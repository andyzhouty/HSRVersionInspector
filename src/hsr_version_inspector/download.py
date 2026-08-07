from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn

from .data import VersionRecord


BASE_URL = "https://static.nanoka.cc/hsr"
CONFIG_BASE_URL = (
    "https://gitlab.com/Dimbreath/turnbasedgamedata/-/raw/main/ExcelOutput"
)
DATA_DIR = Path("data")
DOWNLOAD_MODES = ("character", "lightcone", "maze", "story", "boss", "peak")
CONFIG_FILES = ("HardLevelGroup.json", "EliteGroup.json", "InfiniteEliteGroup.json")
DownloadStatus = Literal["downloaded", "skipped", "missing", "failed"]
console = Console()


@dataclass(frozen=True)
class DownloadTarget:
    version: str
    mode: str
    resource_id: str

    @property
    def url(self) -> str:
        parts = (
            quote(self.version, safe=""),
            "zh",
            quote(self.mode, safe=""),
            f"{quote(self.resource_id, safe='')}.json",
        )
        return f"{BASE_URL}/{'/'.join(parts)}"

    @property
    def relative_path(self) -> Path:
        return Path(self.version) / "zh" / self.mode / f"{self.resource_id}.json"


@dataclass(frozen=True)
class ConfigDownloadTarget:
    file_name: str

    @property
    def url(self) -> str:
        return f"{CONFIG_BASE_URL}/{self.file_name}"

    @property
    def relative_path(self) -> Path:
        return Path("config") / self.file_name


@dataclass(frozen=True)
class DownloadResult:
    target: DownloadTarget | ConfigDownloadTarget
    status: DownloadStatus
    error: str | None = None


def iter_download_targets(catalog: tuple[VersionRecord, ...]) -> tuple[DownloadTarget, ...]:
    """Build unique download targets; the version field is only a URL segment."""
    targets: list[DownloadTarget] = []
    seen: set[tuple[str, str, str]] = set()
    for record in catalog:
        for version in record.versions:
            resources = {
                "character": record.character,
                "lightcone": record.lightcone,
                "maze": (record.maze,),
                "story": (record.story,),
                "boss": (record.boss,),
                "peak": (record.peak,),
            }
            for mode in DOWNLOAD_MODES:
                for resource_id in resources[mode]:
                    if not resource_id:
                        continue
                    key = (version, mode, resource_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    targets.append(DownloadTarget(*key))
    return tuple(targets)


def _download_remote_target(
    target: DownloadTarget | ConfigDownloadTarget,
    output_dir: Path = DATA_DIR,
    opener=urlopen,
) -> DownloadResult:
    request = Request(
        target.url,
        headers={"User-Agent": "hsr-version-inspector/0.1"},
    )
    destination = output_dir / target.relative_path
    if destination.is_file():
        return DownloadResult(target, "skipped")
    try:
        with opener(request, timeout=15) as response:
            content = response.read()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, destination)
    except HTTPError as error:
        if error.code == 404:
            return DownloadResult(target, "missing", "HTTP 404")
        return DownloadResult(target, "failed", f"HTTP {error.code}")
    except (OSError, URLError, TimeoutError) as error:
        return DownloadResult(target, "failed", str(error))
    return DownloadResult(target, "downloaded")


def download_target(
    target: DownloadTarget,
    output_dir: Path = DATA_DIR,
    opener=urlopen,
) -> DownloadResult:
    return _download_remote_target(target, output_dir, opener)


def download_config_target(
    target: ConfigDownloadTarget,
    output_dir: Path = DATA_DIR,
    opener=urlopen,
) -> DownloadResult:
    return _download_remote_target(target, output_dir, opener)


def _monster_template_id(monster_id: int | str) -> str:
    value = str(monster_id)
    return value[:-2] if len(value) > 7 else value


def _monster_references(value: object) -> tuple[int, ...]:
    references: list[int] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if (
                re.fullmatch(r"boss_monster_id\d*", key)
                or re.fullmatch(r"npc_monster_id_list\d*", key)
                or re.fullmatch(r"monster\d+", key)
                or key == "monster_group_id_list"
            ):
                if isinstance(nested, (int, str)) and str(nested).isdigit():
                    references.append(int(nested))
                elif isinstance(nested, list):
                    references.extend(
                        int(item) for item in nested if isinstance(item, (int, str)) and str(item).isdigit()
                    )
            references.extend(_monster_references(nested))
    elif isinstance(value, list):
        for nested in value:
            references.extend(_monster_references(nested))
    return tuple(references)


def iter_monster_targets(
    catalog: tuple[VersionRecord, ...],
    data_dir: Path = DATA_DIR,
) -> tuple[DownloadTarget, ...]:
    """Find monster resources referenced by downloaded high-mode configs."""
    targets: list[DownloadTarget] = []
    seen: set[tuple[str, str, str]] = set()
    for record in catalog:
        for version in record.versions:
            resources = {
                "maze": (record.maze,),
                "story": (record.story,),
                "boss": (record.boss,),
                "peak": (record.peak,),
            }
            for mode, resource_ids in resources.items():
                for resource_id in resource_ids:
                    if not resource_id:
                        continue
                    resource_path = data_dir / version / "zh" / mode / f"{resource_id}.json"
                    try:
                        with resource_path.open(encoding="utf-8") as file:
                            payload = json.load(file)
                    except (OSError, json.JSONDecodeError):
                        continue
                    for monster_id in _monster_references(payload):
                        target = DownloadTarget(
                            version,
                            "monster",
                            _monster_template_id(monster_id),
                        )
                        target_key = (target.version, target.mode, target.resource_id)
                        if target_key in seen:
                            continue
                        seen.add(target_key)
                        targets.append(target)
    return tuple(targets)


def _download_targets(
    targets: tuple[DownloadTarget | ConfigDownloadTarget, ...],
    description: str,
) -> list[DownloadResult]:
    if not targets:
        return []

    results: list[DownloadResult] = []
    progress_columns = (
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    )
    with Progress(*progress_columns, console=console) as progress:
        task = progress.add_task(description, total=len(targets))
        with ThreadPoolExecutor(max_workers=8) as executor:
            pending = {
                executor.submit(_download_remote_target, target): target
                for target in targets
            }
            for future in as_completed(pending):
                results.append(future.result())
                progress.advance(task)
    return results


def download_all(catalog: tuple[VersionRecord, ...]) -> None:
    catalog_targets = iter_download_targets(catalog)
    catalog_results = _download_targets(catalog_targets, "正在下载目录资源")

    monster_targets = iter_monster_targets(catalog)
    monster_results = _download_targets(monster_targets, "正在下载敌人资源")
    config_targets = tuple(ConfigDownloadTarget(file_name) for file_name in CONFIG_FILES)
    config_results = _download_targets(config_targets, "正在下载倍率配置")
    results = [*catalog_results, *monster_results, *config_results]
    if not results:
        console.print("[yellow]未找到可下载的资源。[/yellow]")
        return

    downloaded = sum(result.status == "downloaded" for result in results)
    skipped = sum(result.status == "skipped" for result in results)
    missing = sum(result.status == "missing" for result in results)
    failures = [result for result in results if result.status == "failed"]

    console.print(
        f"已下载 {downloaded} 个资源，跳过 {skipped} 个已有资源，"
        f"保存到 [bold]data/[/bold]。"
    )
    if missing:
        console.print(f"[yellow]{missing} 个资源未找到（HTTP 404）。[/yellow]")
    if failures:
        console.print(f"[red]{len(failures)} 个资源下载失败。[/red]")
        for failure in failures[:10]:
            console.print(f"[red]— {failure.target.url}：{failure.error}[/red]")

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from itertools import islice
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from ..data import FullCatalog, VersionRecord, latest_release, load_full_catalog
from ..download.models import ConfigDownloadTarget, DownloadResult, DownloadTarget
from ..download.targets import (
    DOWNLOAD_MODES,
    _catalog_with_versions,
    _retained_download_targets,
    _unique_download_targets,
    iter_full_monster_targets,
    iter_monster_targets,
    iter_sync_download_targets,
)
from ..download.transport import (
    _download_remote_target,
)
from ..paths import DATA_DIR
from .runtime import app_module

CONFIG_FILES = ("HardLevelGroup.json", "EliteGroup.json", "InfiniteEliteGroup.json")
DEFAULT_DOWNLOAD_WORKERS = 40
MAX_DOWNLOAD_WORKERS = 64
console = Console()


def register(app: typer.Typer, command: Callable[..., Any]) -> None:
    app.command("download")(command)


def register_cleanup(app: typer.Typer, command: Callable[..., Any]) -> None:
    app.command("cleanup")(command)


def download_command() -> None:
    """同步最新版本全量数据和历史版本所需数据。"""
    runtime = app_module()
    download_all(runtime._load_data(), runtime._load_full_data())


def cleanup_command() -> None:
    """删除历史版本中不再被 show 或 diff 使用的全量缓存。"""
    runtime = app_module()
    removed = cleanup_data(runtime._load_data(), runtime._load_full_data())
    if removed:
        console.print(f"已清理 {len(removed)} 个历史版本的冗余数据文件。")
    else:
        console.print("[dim]没有可清理的历史版本冗余数据。[/dim]")


def _remove_stale_resources(
    retained_targets: tuple[DownloadTarget, ...],
    data_dir: Path,
) -> tuple[Path, ...]:
    if not data_dir.is_dir():
        return ()
    retained_paths = {target.relative_path for target in retained_targets}
    known_modes = {*DOWNLOAD_MODES, "monster"}
    stale_paths = tuple(
        path
        for path in sorted(data_dir.glob("*/zh/*/*.json"))
        if len(path.relative_to(data_dir).parts) == 4
        and path.relative_to(data_dir).parts[1] == "zh"
        and path.relative_to(data_dir).parts[2] in known_modes
        and path.relative_to(data_dir) not in retained_paths
    )
    for path in stale_paths:
        path.unlink()
    for path in stale_paths:
        directory = path.parent
        while directory != data_dir:
            try:
                directory.rmdir()
            except OSError:
                break
            directory = directory.parent
    return stale_paths


def cleanup_data(
    catalog: tuple[VersionRecord, ...],
    full_catalog: FullCatalog | None = None,
    data_dir: Path = DATA_DIR,
) -> tuple[Path, ...]:
    """Remove redundant full-cache files from historical versions."""
    full_catalog = full_catalog or load_full_catalog()
    return _remove_stale_resources(
        _retained_download_targets(catalog, full_catalog, data_dir),
        data_dir,
    )


def _download_worker_count() -> int:
    configured = os.environ.get("HVI_DOWNLOAD_WORKERS")
    if configured is None:
        return DEFAULT_DOWNLOAD_WORKERS
    try:
        return min(max(int(configured), 1), MAX_DOWNLOAD_WORKERS)
    except ValueError:
        return DEFAULT_DOWNLOAD_WORKERS


def _download_targets(
    targets: tuple[DownloadTarget | ConfigDownloadTarget, ...],
    description: str,
    *,
    workers: int | None = None,
    console_obj: Console | None = None,
    downloader: Callable[
        [DownloadTarget | ConfigDownloadTarget], DownloadResult
    ] = _download_remote_target,
) -> list[DownloadResult]:
    if not targets:
        return []

    worker_count = workers if workers is not None else _download_worker_count()
    if worker_count < 1:
        raise ValueError("下载并发数必须至少为 1。")
    results: list[DownloadResult] = []
    progress_columns = (
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    )
    with Progress(*progress_columns, console=console_obj or console) as progress:
        task = progress.add_task(
            f"{description}（{worker_count} 路并发）",
            total=len(targets),
        )
        target_iterator = iter(targets)
        max_pending = worker_count * 2
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            pending = {
                executor.submit(downloader, target)
                for target in islice(target_iterator, max_pending)
            }
            while pending:
                completed, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in completed:
                    pending.remove(future)
                    results.append(future.result())
                    progress.advance(task)
                    try:
                        target = next(target_iterator)
                    except StopIteration:
                        continue
                    pending.add(executor.submit(downloader, target))
    return results


def download_all(
    catalog: tuple[VersionRecord, ...],
    full_catalog: FullCatalog | None = None,
) -> None:
    """Sync the newest full cache and historical version-specific resources."""
    full_catalog = full_catalog or load_full_catalog()
    newest_catalog = _catalog_with_versions(catalog, {latest_release(catalog)})
    catalog_targets = iter_sync_download_targets(catalog, full_catalog)
    catalog_results = _download_targets(catalog_targets, "正在下载资源")

    monster_targets = _unique_download_targets(
        iter_full_monster_targets(newest_catalog, full_catalog),
        iter_monster_targets(catalog),
    )
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
    removed = _remove_stale_resources(
        _unique_download_targets(catalog_targets, monster_targets),
        DATA_DIR,
    )
    if removed:
        console.print(f"已清理 {len(removed)} 个历史版本的冗余数据文件。")

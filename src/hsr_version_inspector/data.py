from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PACKAGE_DATA_FILE = Path(__file__).with_name("versionID.json")
PACKAGE_FULL_DATA_FILE = Path(__file__).with_name("full.json")
DATA_FILE = Path("versionID.json")
FULL_DATA_FILE = Path("full.json")


@dataclass(frozen=True)
class FullCatalog:
    """The complete set of resource IDs that can be queried in every version."""

    character: tuple[str, ...]
    lightcone: tuple[str, ...]
    maze: tuple[str, ...]
    story: tuple[str, ...]
    boss: tuple[str, ...]
    peak: tuple[str, ...]

    def resource_ids(self, mode: str) -> tuple[str, ...]:
        try:
            return getattr(self, mode)
        except AttributeError as error:
            raise ValueError(f"不支持的完整数据模式 {mode!r}。") from error

    def contains(self, mode: str, resource_id: str | int) -> bool:
        return str(resource_id) in self.resource_ids(mode)


@dataclass(frozen=True)
class VersionRecord:
    name: str
    versions: tuple[str, ...]
    character: tuple[str, ...]
    lightcone: tuple[str, ...]
    maze: str
    story: str
    boss: str
    peak: str

    @property
    def content_count(self) -> int:
        return len(self.character) + len(self.lightcone)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _id_range(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"完整数据目录项 {name!r} 必须包含起止两个 ID。")
    try:
        start, end = (int(item) for item in value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"完整数据目录项 {name!r} 的 ID 必须是整数。") from error
    if start > end:
        raise ValueError(f"完整数据目录项 {name!r} 的起始 ID 不能大于结束 ID。")
    return tuple(str(resource_id) for resource_id in range(start, end + 1))


def load_catalog(path: Path | None = None) -> tuple[VersionRecord, ...]:
    """Load version metadata from a JSON catalog."""
    if path is None:
        path = DATA_FILE if DATA_FILE.is_file() else PACKAGE_DATA_FILE
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError("版本目录根节点必须是 JSON 对象。")

    records: list[VersionRecord] = []
    for name, raw_record in payload.items():
        if not isinstance(raw_record, dict):
            raise ValueError(f"版本目录项 {name!r} 必须是对象。")
        records.append(
            VersionRecord(
                name=str(name),
                versions=_string_tuple(raw_record.get("version")),
                character=_string_tuple(raw_record.get("character")),
                lightcone=_string_tuple(raw_record.get("lightcone")),
                maze=str(raw_record.get("maze", "")),
                story=str(raw_record.get("story", "")),
                boss=str(raw_record.get("boss", "")),
                peak=str(raw_record.get("peak", "")),
            )
        )
    return tuple(records)


def load_full_catalog(path: Path | None = None) -> FullCatalog:
    """Load the complete resource index used for ID-based retrieval."""
    if path is None:
        path = FULL_DATA_FILE if FULL_DATA_FILE.is_file() else PACKAGE_FULL_DATA_FILE
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("完整数据目录根节点必须是 JSON 对象。")
    return FullCatalog(
        character=_string_tuple(payload.get("character_id")),
        lightcone=_string_tuple(payload.get("lightcone_id")),
        maze=_id_range(payload.get("maze"), "maze"),
        story=_id_range(payload.get("story"), "story"),
        boss=_id_range(payload.get("boss"), "boss"),
        peak=_id_range(payload.get("peak"), "peak"),
    )


def find_version(catalog: tuple[VersionRecord, ...], name: str) -> VersionRecord:
    for record in catalog:
        if record.name == name:
            return record
    raise KeyError(name)


def find_release(catalog: tuple[VersionRecord, ...], release: str) -> VersionRecord:
    for record in catalog:
        if release in record.versions:
            return record
    raise KeyError(release)


def latest_release(catalog: tuple[VersionRecord, ...]) -> str:
    """Return the newest numeric dotted release from the version catalog."""
    versions = tuple(
        version
        for record in catalog
        for version in record.versions
    )
    if not versions:
        raise ValueError("版本目录中没有可查询的版本。")
    try:
        return max(
            versions,
            key=lambda version: tuple(int(part) for part in version.split(".")),
        )
    except ValueError as error:
        raise ValueError("版本目录中包含无法排序的版本号。") from error

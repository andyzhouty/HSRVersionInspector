from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PACKAGE_DATA_FILE = Path(__file__).with_name("versionID.json")
DATA_FILE = Path("versionID.json")


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

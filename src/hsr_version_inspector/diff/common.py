"""Shared validation and raw JSON comparison helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..data import VersionRecord
from ..output.labels import MODE_LABELS
from ..paths import DATA_DIR
from .models import DiffReport, JsonChange, ResourceDiff

DIFF_MODES = (
    "character",
    "lightcone",
    "maze",
    "story",
    "boss",
    "peak",
    "knight",
    "king",
    "hard-king",
)
INTERNAL_DIFF_MODES = {*DIFF_MODES, "story"}
MAX_STORED_CHANGES = 80
MISSING = object()


def version_family(version: str) -> str:
    parts = version.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else version


def resource_ids(record: VersionRecord, mode: str) -> tuple[str, ...]:
    value = getattr(record, mode)
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(value)


def resource_path(data_root: Path, version: str, mode: str, resource_id: str) -> Path:
    return data_root / version / "zh" / mode / f"{resource_id}.json"


def read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return MISSING


def path_key(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}[{json.dumps(key, ensure_ascii=False)}]"


def compare_values(
    before: Any,
    after: Any,
    path: str,
    changes: list[JsonChange],
) -> int:
    if before is MISSING and after is MISSING:
        return 0
    if before is MISSING or after is MISSING:
        if len(changes) < MAX_STORED_CHANGES:
            changes.append(JsonChange(path, before, after))
        return 1
    if type(before) is not type(after):
        if len(changes) < MAX_STORED_CHANGES:
            changes.append(JsonChange(path, before, after))
        return 1
    if isinstance(before, dict):
        total = 0
        keys = sorted(set(before) | set(after), key=str)
        for key in keys:
            total += compare_values(
                before.get(key, MISSING),
                after.get(key, MISSING),
                path_key(path, str(key)),
                changes,
            )
        return total
    if isinstance(before, list):
        total = 0
        for index in range(max(len(before), len(after))):
            old_value = before[index] if index < len(before) else MISSING
            new_value = after[index] if index < len(after) else MISSING
            total += compare_values(old_value, new_value, path_key(path, index), changes)
        return total
    if before == after:
        return 0
    if len(changes) < MAX_STORED_CHANGES:
        changes.append(JsonChange(path, before, after))
    return 1


def mode_label(mode: str) -> str:
    if mode.startswith("story "):
        return f"虚构节点 {mode.removeprefix('story ')}"
    return MODE_LABELS.get(mode, mode)


def supported_modes_text() -> str:
    return "、".join(f"{mode_label(mode)}（{mode}）" for mode in DIFF_MODES)


def validate_request(
    record_one: VersionRecord,
    record_two: VersionRecord,
    version_one: str,
    version_two: str,
    mode: str,
) -> None:
    if mode not in INTERNAL_DIFF_MODES:
        raise ValueError(f"不支持的比较模式 {mode!r}。")
    if version_one == version_two:
        raise ValueError("两个版本必须是不同的版本。")
    if version_family(version_one) != version_family(version_two):
        raise ValueError("只能比较主版本号和次版本号相同的版本线。")
    if record_one.name != record_two.name:
        raise ValueError("只能比较同一版本目录项中的版本。")
    resource_mode = "peak" if mode in {"knight", "king", "hard-king"} else mode
    if not resource_ids(record_one, resource_mode) or not resource_ids(record_two, resource_mode):
        raise ValueError(f"此版本线未配置 {mode_label(mode)} 资源。")


def compare_versions(
    version_one: str,
    version_two: str,
    mode: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> DiffReport:
    validate_request(record_one, record_two, version_one, version_two, mode)
    ids = tuple(dict.fromkeys((*resource_ids(record_one, mode), *resource_ids(record_two, mode))))
    resources: list[ResourceDiff] = []
    for resource_id in ids:
        before = read_json(resource_path(data_root, version_one, mode, resource_id))
        after = read_json(resource_path(data_root, version_two, mode, resource_id))
        changes: list[JsonChange] = []
        change_count = compare_values(before, after, "$", changes)
        if before is MISSING and after is MISSING:
            status = "missing"
        elif before is MISSING:
            status = "added"
        elif after is MISSING:
            status = "removed"
        elif change_count:
            status = "changed"
        else:
            status = "unchanged"
        resources.append(ResourceDiff(resource_id, status, change_count, tuple(changes)))
    return DiffReport(version_one, version_two, mode, tuple(resources))


def format_value(value: Any) -> str:
    if value is MISSING:
        return "<缺失>"
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{text[:177]}..." if len(text) > 180 else text


def format_name_change(name_one: str, name_two: str) -> str:
    return name_one if name_one == name_two else f"{name_one} → {name_two}"


def is_missing(value: Any) -> bool:
    return value is MISSING


def highmode_change_subject(change: Any) -> str:
    if change.subject is not None:
        return change.subject
    if ": " in change.label:
        return change.label.split(": ", 1)[1]
    return change.label


def highmode_change_wave(change: Any) -> int | None:
    if change.wave is not None:
        return change.wave
    match = re.match(r"Wave (\d+): ", change.label)
    return int(match.group(1)) if match else None

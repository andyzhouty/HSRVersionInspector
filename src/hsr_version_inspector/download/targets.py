"""Download target discovery and cache retention rules."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..data import FullCatalog, VersionRecord, latest_release
from ..paths import DATA_DIR
from .models import DownloadTarget

DOWNLOAD_MODES = ("character", "lightcone", "maze", "story", "boss", "peak")

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


def iter_full_download_targets(
    catalog: tuple[VersionRecord, ...],
    full_catalog: FullCatalog,
) -> tuple[DownloadTarget, ...]:
    """Build every resource target described by ``full.json``."""
    targets: list[DownloadTarget] = []
    seen: set[tuple[str, str, str]] = set()
    for record in catalog:
        for version in record.versions:
            for mode in DOWNLOAD_MODES:
                for resource_id in full_catalog.resource_ids(mode):
                    key = (version, mode, resource_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    targets.append(DownloadTarget(*key))
    return tuple(targets)


def _catalog_with_versions(
    catalog: tuple[VersionRecord, ...],
    versions: set[str],
) -> tuple[VersionRecord, ...]:
    records: list[VersionRecord] = []
    for record in catalog:
        selected_versions = tuple(
            version for version in record.versions if version in versions
        )
        if not selected_versions:
            continue
        records.append(
            VersionRecord(
                record.name,
                selected_versions,
                record.character,
                record.lightcone,
                record.maze,
                record.story,
                record.boss,
                record.peak,
            )
        )
    return tuple(records)


def _unique_download_targets(
    *target_groups: tuple[DownloadTarget, ...],
) -> tuple[DownloadTarget, ...]:
    targets: list[DownloadTarget] = []
    seen: set[tuple[str, str, str]] = set()
    for group in target_groups:
        for target in group:
            key = (target.version, target.mode, target.resource_id)
            if key not in seen:
                seen.add(key)
                targets.append(target)
    return tuple(targets)


def iter_sync_download_targets(
    catalog: tuple[VersionRecord, ...],
    full_catalog: FullCatalog,
) -> tuple[DownloadTarget, ...]:
    """Keep full resources only for the newest version and legacy targets for all releases."""
    newest_catalog = _catalog_with_versions(catalog, {latest_release(catalog)})
    return _unique_download_targets(
        iter_full_download_targets(newest_catalog, full_catalog),
        iter_download_targets(catalog),
    )
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


def iter_full_monster_targets(
    catalog: tuple[VersionRecord, ...],
    full_catalog: FullCatalog,
    data_dir: Path = DATA_DIR,
) -> tuple[DownloadTarget, ...]:
    """Find monsters referenced by the downloaded full high-mode index."""
    targets: list[DownloadTarget] = []
    seen: set[tuple[str, str, str]] = set()
    resources = {
        mode: full_catalog.resource_ids(mode)
        for mode in ("maze", "story", "boss", "peak")
    }
    for record in catalog:
        for version in record.versions:
            for mode, resource_ids in resources.items():
                for resource_id in resource_ids:
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


def _retained_download_targets(
    catalog: tuple[VersionRecord, ...],
    full_catalog: FullCatalog,
    data_dir: Path,
) -> tuple[DownloadTarget, ...]:
    newest_catalog = _catalog_with_versions(catalog, {latest_release(catalog)})
    resource_targets = iter_sync_download_targets(catalog, full_catalog)
    return _unique_download_targets(
        resource_targets,
        iter_full_monster_targets(newest_catalog, full_catalog, data_dir),
        iter_monster_targets(catalog, data_dir),
    )

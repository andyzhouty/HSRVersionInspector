"""Light-cone comparison domain logic."""

from __future__ import annotations

from pathlib import Path

from ..data import VersionRecord
from ..lightcone import LightConeView, load_lightcone
from ..paths import DATA_DIR
from .common import resource_ids, validate_request
from .models import LightConeChange, LightConeDiffReport, LightConeSectionDiff


def _lightcone_text_map(view: LightConeView) -> dict[str, str]:
    return {
        "等级": f"{view.level}级",
        "稀有度": f"{view.rarity}星",
        "命途": view.path,
        "生命值": view.hp,
        "攻击力": view.attack,
        "防御力": view.defence,
    }


def _lightcone_effect_map(view: LightConeView) -> dict[str, str]:
    return {view.refinement_name: view.description}


def section_change_sort_key(label: str) -> tuple[int, int | str]:
    order = {"等级": -3, "稀有度": -2, "命途": -1, "生命值": 0, "攻击力": 1, "防御力": 2}
    return (0, order[label]) if label in order else (1, label)


def _lightcone_section(
    name: str,
    before: dict[str, str],
    after: dict[str, str],
) -> LightConeSectionDiff:
    changes: list[LightConeChange] = []
    for label in sorted(set(before) | set(after), key=section_change_sort_key):
        old = before.get(label)
        new = after.get(label)
        if old == new:
            continue
        kind = "added" if old is None else "removed" if new is None else "changed"
        changes.append(LightConeChange(label, old, new, kind))
    return LightConeSectionDiff(name, "changed" if changes else "unchanged", tuple(changes))


def compare_lightcone_versions(
    version_one: str,
    version_two: str,
    node: int,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> LightConeDiffReport:
    if node < 1:
        raise ValueError("光锥比较需要提供正整数序号，例如 lightcone 1。")
    validate_request(record_one, record_two, version_one, version_two, "lightcone")
    ids_one = resource_ids(record_one, "lightcone")
    ids_two = resource_ids(record_two, "lightcone")
    if node > len(ids_one) or node > len(ids_two):
        raise ValueError(f"光锥序号 {node} 在两个版本中未同时存在。")
    lightcone_id_one = ids_one[node - 1]
    lightcone_id_two = ids_two[node - 1]
    before = load_lightcone(version_one, lightcone_id_one, data_root)
    after = load_lightcone(version_two, lightcone_id_two, data_root)
    sections = (
        _lightcone_section("基础属性", _lightcone_text_map(before), _lightcone_text_map(after)),
        _lightcone_section("光锥效果", _lightcone_effect_map(before), _lightcone_effect_map(after)),
    )
    return LightConeDiffReport(
        version_one,
        version_two,
        lightcone_id_one,
        lightcone_id_two,
        before.name,
        after.name,
        sections,
    )


def compare_all_lightcone_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[LightConeDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "lightcone")
    ids_one = resource_ids(record_one, "lightcone")
    ids_two = resource_ids(record_two, "lightcone")
    if len(ids_one) != len(ids_two):
        raise ValueError("不指定光锥序号时，两个版本必须拥有相同长度的光锥列表。")
    return tuple(
        compare_lightcone_versions(
            version_one,
            version_two,
            index,
            record_one,
            record_two,
            data_root,
        )
        for index in range(1, len(ids_one) + 1)
    )

"""Character comparison domain logic."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..character import CharacterView, load_character
from ..data import VersionRecord
from ..paths import DATA_DIR
from .common import resource_ids, validate_request
from .models import (
    CharacterChange,
    CharacterDiffReport,
    CharacterSectionDiff,
)

BASE_STAT_ORDER = {
    "命途": -1,
    "生命值": 0,
    "攻击力": 1,
    "防御力": 2,
    "速度": 3,
}
CHARACTER_SKILL_LABEL = re.compile(r"^(?P<type>.+?) \d+级 · (?P<name>.+)$")


def section_change_sort_key(label: str) -> tuple[int, int | str]:
    stat_name = label.removeprefix("基础")
    if stat_name in BASE_STAT_ORDER:
        return (0, BASE_STAT_ORDER[stat_name])
    return (1, label)


def _character_skill_map(view: CharacterView, memosprite: bool = False) -> dict[str, str]:
    skills = view.memosprite_skills if memosprite else view.skills
    return {
        f"{skill.type_name} {skill.level}级 · {skill.name}": skill.description
        for skill in skills
    }


def _character_text_map(entries: tuple[Any, ...]) -> dict[str, str]:
    return {entry.name: entry.description for entry in entries}


def _character_base_stat_map(view: CharacterView) -> dict[str, str]:
    stats = {"命途": view.path}
    if view.base_stats is None:
        return stats
    stats.update({
        "基础生命值": view.base_stats.hp,
        "基础攻击力": view.base_stats.attack,
        "基础防御力": view.base_stats.defence,
        "基础速度": view.base_stats.speed,
    })
    return stats


def _character_eidolon_map(view: CharacterView) -> dict[str, str]:
    return {
        f"星魂 {index} · {entry.name}": entry.description
        for index, entry in enumerate(view.eidolons, 1)
    }


def _character_section(
    name: str,
    before: dict[str, str],
    after: dict[str, str],
) -> CharacterSectionDiff:
    changes: list[CharacterChange] = []
    for label in sorted(set(before) | set(after), key=section_change_sort_key):
        old = before.get(label)
        new = after.get(label)
        if old == new:
            continue
        kind = "added" if old is None else "removed" if new is None else "changed"
        changes.append(CharacterChange(label, old, new, kind))
    return CharacterSectionDiff(name, "changed" if changes else "unchanged", tuple(changes))


def compare_character_versions(
    version_one: str,
    version_two: str,
    node: int | None,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> CharacterDiffReport:
    if node is None or node < 1:
        raise ValueError("角色比较需要提供序号，例如 character 1。")
    validate_request(record_one, record_two, version_one, version_two, "character")
    ids_one = resource_ids(record_one, "character")
    ids_two = resource_ids(record_two, "character")
    if node > len(ids_one) or node > len(ids_two):
        raise ValueError(f"角色序号 {node} 在两个版本中未同时存在。")
    character_id_one = ids_one[node - 1]
    character_id_two = ids_two[node - 1]
    before = load_character(version_one, character_id_one, data_root)
    after = load_character(version_two, character_id_two, data_root)
    sections: list[CharacterSectionDiff] = []
    if before.base_stats or after.base_stats or before.path != after.path:
        sections.append(
            _character_section(
                "基础属性",
                _character_base_stat_map(before),
                _character_base_stat_map(after),
            )
        )
    sections.append(
        _character_section(
            "技能",
            _character_skill_map(before),
            _character_skill_map(after),
        )
    )
    if (
        before.memosprite_name
        or after.memosprite_name
        or before.memosprite_skills
        or after.memosprite_skills
    ):
        sections.append(
            _character_section(
                f"忆灵 · {before.memosprite_name or after.memosprite_name or '-'}",
                _character_skill_map(before, True),
                _character_skill_map(after, True),
            )
        )
    sections.extend(
        [
            _character_section(
                "行迹",
                {
                    **_character_text_map(before.traces),
                    **{
                        f"属性 · {entry.name}": entry.description
                        for entry in before.trace_stats
                    },
                },
                {
                    **_character_text_map(after.traces),
                    **{
                        f"属性 · {entry.name}": entry.description
                        for entry in after.trace_stats
                    },
                },
            ),
            _character_section(
                "特殊效果",
                _character_text_map(before.special_effects),
                _character_text_map(after.special_effects),
            ),
            _character_section(
                "星魂",
                _character_eidolon_map(before),
                _character_eidolon_map(after),
            ),
        ]
    )
    return CharacterDiffReport(
        version_one,
        version_two,
        character_id_one,
        character_id_two,
        before.name,
        after.name,
        tuple(sections),
    )

def compare_all_character_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[CharacterDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "character")
    ids_one = resource_ids(record_one, "character")
    ids_two = resource_ids(record_two, "character")
    if len(ids_one) != len(ids_two):
        raise ValueError(
            "不指定角色序号时，两个版本必须拥有相同长度的角色列表。"
        )
    return tuple(
        compare_character_versions(
            version_one,
            version_two,
            index,
            record_one,
            record_two,
            data_root,
        )
        for index in range(1, len(ids_one) + 1)
    )

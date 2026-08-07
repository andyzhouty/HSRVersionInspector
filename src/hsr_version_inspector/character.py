from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATA_DIR = Path("data")
_PLACEHOLDER = re.compile(r"#(\d+)\[(i|f(\d+))\](%)?")
_TAG = re.compile(r"</?[^>]+>")


@dataclass(frozen=True)
class CharacterSkill:
    type_name: str
    name: str
    level: int
    description: str


@dataclass(frozen=True)
class CharacterText:
    name: str
    description: str


@dataclass(frozen=True)
class CharacterBaseStats:
    hp: str
    attack: str
    defence: str
    speed: str


@dataclass(frozen=True)
class CharacterView:
    version: str
    character_id: str
    name: str
    level: int
    base_stats: CharacterBaseStats | None
    skills: tuple[CharacterSkill, ...]
    memosprite_name: str | None
    memosprite_skills: tuple[CharacterSkill, ...]
    traces: tuple[CharacterText, ...]
    trace_stats: tuple[CharacterText, ...]
    special_effects: tuple[CharacterText, ...]
    eidolons: tuple[CharacterText, ...]


def group_skill_entries(
    entries: tuple[CharacterSkill, ...],
) -> tuple[tuple[CharacterSkill, ...], ...]:
    """Group skills by type while preserving the first-seen type order."""
    grouped: dict[str, list[CharacterSkill]] = {}
    for entry in entries:
        grouped.setdefault(entry.type_name, []).append(entry)
    return tuple(tuple(grouped[type_name]) for type_name in grouped)


def skill_group_title(group: tuple[CharacterSkill, ...]) -> str:
    """Return the shared type and level label for a skill group."""
    levels = {entry.level for entry in group}
    if len(levels) == 1:
        return f"{group[0].type_name} {group[0].level}级"
    return group[0].type_name


def skill_entry_title(
    group: tuple[CharacterSkill, ...],
    entry: CharacterSkill,
) -> str:
    """Avoid repeating a shared level label inside a skill group."""
    if len({item.level for item in group}) == 1:
        return entry.name
    return f"{entry.name} {entry.level}级"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"文件 {path} 应为 JSON 对象。")
    return payload


def _format_number(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        if float(value).is_integer():
            return str(int(value))
        return f"{value:g}"
    return str(value)


def _format_parameter(value: Any, formatter: str, percent: bool) -> str:
    if not isinstance(value, (int, float)):
        return str(value)
    number = float(value) * 100 if percent else float(value)
    if formatter == "i":
        return _format_number(round(number) if percent else value)
    digits = int(formatter[1:])
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def _format_level_stat(base: Any, increment: Any, level: int) -> str:
    if not isinstance(base, (int, float)):
        return _format_stat(base)
    if not isinstance(increment, (int, float)):
        increment = 0
    return f"{float(base) + float(increment) * (level - 1):.2f}"


def _format_stat(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.2f}"
    return str(value)


def _format_speed(value: Any) -> str:
    return "-" if value is None else _format_number(value)


def format_description(text: str, params: list[Any] | tuple[Any, ...] = ()) -> str:
    """Expand game placeholders and remove the HTML-like formatting tags."""

    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if index >= len(params):
            return match.group(0)
        value = _format_parameter(
            params[index],
            match.group(2),
            bool(match.group(4)),
        )
        return f"{value}%" if match.group(4) else value

    text = _PLACEHOLDER.sub(replace, text)
    return html.unescape(_TAG.sub("", text)).replace(r"\n", "\n")


def _level_data(skill: dict[str, Any], target_level: int) -> tuple[int, dict[str, Any]]:
    levels = skill.get("level")
    if not isinstance(levels, dict) or not levels:
        return 1, {}
    numeric_levels = sorted(
        (int(level), value)
        for level, value in levels.items()
        if str(level).isdigit() and isinstance(value, dict)
    )
    if not numeric_levels:
        return 1, {}
    for level, value in numeric_levels:
        if level == target_level:
            return level, value
    return max(numeric_levels, key=lambda item: item[0])


def _target_level(type_name: str, fallback: int) -> int:
    return {
        "普攻": 6,
        "战技": 10,
        "终结技": 10,
        "天赋": 10,
        "忆灵技": 6,
        "忆灵天赋": 6,
        "欢愉技": 10,
        "助战技": 10,
    }.get(type_name, fallback)


def _skill_view(skill: dict[str, Any], target_level: int) -> CharacterSkill:
    level, level_data = _level_data(skill, target_level)
    params = level_data.get("param_list", [])
    if not isinstance(params, list):
        params = []
    return CharacterSkill(
        type_name=str(skill.get("type_name", "")),
        name=str(skill.get("name", "")),
        level=level,
        description=format_description(str(skill.get("desc", "")), params),
    )


def _load_skills(skills: Any) -> tuple[CharacterSkill, ...]:
    if not isinstance(skills, dict):
        return ()
    result: list[CharacterSkill] = []
    for skill in skills.values():
        if not isinstance(skill, dict):
            continue
        type_name = skill.get("type_name")
        if not isinstance(type_name, str) or not type_name:
            continue
        description = skill.get("desc")
        if (
            skill.get("name") is None
            or not isinstance(description, str)
            or not description.strip()
        ):
            continue
        levels = skill.get("level", {})
        fallback = max(
            (int(level) for level in levels if str(level).isdigit()),
            default=1,
        ) if isinstance(levels, dict) else 1
        result.append(_skill_view(skill, _target_level(type_name, fallback)))
    return tuple(result)


def _load_base_stats(stats: Any, level: int) -> CharacterBaseStats | None:
    if not isinstance(stats, dict):
        return None
    candidates = [
        (int(key), value)
        for key, value in stats.items()
        if str(key).isdigit() and isinstance(value, dict)
    ]
    if not candidates:
        return None
    _, values = max(candidates, key=lambda item: item[0])
    return CharacterBaseStats(
        hp=_format_level_stat(values.get("hp_base"), values.get("hp_add"), level),
        attack=_format_level_stat(
            values.get("attack_base"), values.get("attack_add"), level
        ),
        defence=_format_level_stat(
            values.get("defence_base"), values.get("defence_add"), level
        ),
        speed=_format_speed(values.get("speed_base")),
    )


def _status_info(status: dict[str, Any]) -> tuple[str, float, bool, str] | None:
    name = str(status.get("name", status.get("property_type", "")))
    value = status.get("value", "")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    property_type = str(status.get("property_type", ""))
    is_percent = (
        property_type.endswith("Ratio")
        or property_type.endswith("RatioBase")
        or property_type in {
        "CriticalChanceBase",
        "CriticalDamageBase",
        }
    )
    return name, float(value), is_percent, property_type


def _load_traces(
    skill_trees: Any,
) -> tuple[tuple[CharacterText, ...], tuple[CharacterText, ...]]:
    if not isinstance(skill_trees, dict):
        return (), ()
    traces: list[CharacterText] = []
    stat_totals: dict[tuple[str, bool, str], float] = {}
    for levels in skill_trees.values():
        if not isinstance(levels, dict) or not levels:
            continue
        point = next(
            (value for value in levels.values() if isinstance(value, dict)),
            None,
        )
        if point is None or point.get("point_type") not in (1, 3):
            continue
        name = str(point.get("point_name") or "")
        if point.get("point_type") == 1:
            statuses = point.get("status_add_list", [])
            if isinstance(statuses, list):
                for status in statuses:
                    if not isinstance(status, dict):
                        continue
                    info = _status_info(status)
                    if info is None:
                        continue
                    status_name, value, is_percent, property_type = info
                    key = (status_name, is_percent, property_type)
                    stat_totals[key] = stat_totals.get(key, 0) + value
            continue
        if not name:
            continue
        params = point.get("param_list", [])
        if not isinstance(params, list):
            params = []
        description = format_description(str(point.get("point_desc") or ""), params)
        if description:
            traces.append(CharacterText(name, description))
    stats = tuple(
        CharacterText(
            name,
            f"+{_format_parameter(value, 'f1', is_percent)}"
            f"{'%' if is_percent else ''}",
        )
        for (name, is_percent, _), value in stat_totals.items()
    )
    return tuple(traces), stats


def _iter_effects(value: Any) -> list[tuple[str, str, list[Any]]]:
    effects: list[tuple[str, str, list[Any]]] = []
    if not isinstance(value, dict):
        return effects
    for item in value.values():
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        description = item.get("desc")
        if name is not None and description is not None:
            params = item.get("param", [])
            effects.append(
                (
                    str(name),
                    str(description),
                    params if isinstance(params, list) else [],
                )
            )
    return effects


def _load_special_effects(payload: dict[str, Any]) -> tuple[CharacterText, ...]:
    effects: list[CharacterText] = []
    seen: set[tuple[str, str]] = set()

    def add_items(value: Any, fallback_params: list[Any] | tuple[Any, ...] = ()) -> None:
        for name, description, params in _iter_effects(value):
            rendered = format_description(description, params or fallback_params)
            key = (name, rendered)
            if key not in seen:
                seen.add(key)
                effects.append(CharacterText(name, rendered))

    skills = payload.get("skills")
    if isinstance(skills, dict):
        for skill in skills.values():
            if isinstance(skill, dict):
                add_items(skill.get("extra"))
    memosprite = payload.get("memosprite")
    if isinstance(memosprite, dict):
        for skill in (memosprite.get("skills") or {}).values():
            if isinstance(skill, dict):
                add_items(skill.get("extra"))
    for rank in (payload.get("ranks") or {}).values():
        if isinstance(rank, dict):
            add_items(rank.get("extra"), rank.get("param_list", []))
    for levels in (payload.get("skill_trees") or {}).values():
        if isinstance(levels, dict):
            for point in levels.values():
                if isinstance(point, dict):
                    add_items(point.get("extra"), point.get("param_list", []))
    add_items(payload.get("unique"))
    return tuple(effects)


def _load_eidolons(ranks: Any) -> tuple[CharacterText, ...]:
    if not isinstance(ranks, dict):
        return ()
    result: list[CharacterText] = []
    for index in range(1, 7):
        rank = ranks.get(str(index))
        if not isinstance(rank, dict):
            continue
        if rank.get("name") is None or rank.get("desc") is None:
            continue
        params = rank.get("param_list", [])
        if not isinstance(params, list):
            params = []
        result.append(
            CharacterText(
                str(rank.get("name", f"星魂 {index}")),
                format_description(str(rank.get("desc", "")), params),
            )
        )
    return tuple(result)


def load_character(
    version: str,
    character_id: str,
    data_root: Path = DATA_DIR,
) -> CharacterView:
    path = data_root / version / "zh" / "character" / f"{character_id}.json"
    payload = _load_json(path)
    memosprite = payload.get("memosprite")
    memosprite_skills = (
        _load_skills(memosprite.get("skills"))
        if isinstance(memosprite, dict)
        else ()
    )
    traces, trace_stats = _load_traces(payload.get("skill_trees"))
    return CharacterView(
        version=version,
        character_id=character_id,
        name=str(payload.get("name", character_id)),
        level=80,
        base_stats=_load_base_stats(payload.get("stats"), 80),
        skills=_load_skills(payload.get("skills")),
        memosprite_name=(
            str(memosprite.get("name"))
            if isinstance(memosprite, dict) and memosprite.get("name")
            else None
        ),
        memosprite_skills=memosprite_skills,
        traces=traces,
        trace_stats=trace_stats,
        special_effects=_load_special_effects(payload),
        eidolons=_load_eidolons(payload.get("ranks")),
    )

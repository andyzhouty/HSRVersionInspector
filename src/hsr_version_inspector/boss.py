from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import DATA_DIR
from .scaling import EnemyScaling, calculate_hp, load_enemy_scaling


@dataclass(frozen=True)
class BossBuff:
    name: str
    description: str


@dataclass(frozen=True)
class BossView:
    version: str
    node: int
    level: int
    name: str
    hp: int
    phases: int
    buffs: tuple[BossBuff, ...]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"文件 {path} 应为 JSON 对象。")
    return payload


def _monster_template_id(monster_id: int | str) -> str:
    value = str(monster_id)
    return value[:-2] if len(value) > 7 else value


def _field_for_node(node: int) -> str:
    return f"boss_monster_id{node}"


def available_boss_nodes(
    version: str,
    resource_id: str,
    data_root: Path = DATA_DIR,
) -> tuple[int, ...]:
    payload = _load_json(data_root / version / "zh" / "boss" / f"{resource_id}.json")
    nodes: set[int] = set()
    has_default_node = False
    for level in payload.get("level", []):
        if not isinstance(level, dict):
            continue
        for key in level:
            match = re.fullmatch(r"boss_monster_id(\d*)", str(key))
            if match:
                if match.group(1):
                    nodes.add(int(match.group(1)))
                else:
                    has_default_node = True
    if has_default_node:
        nodes.add(3 if nodes else 1)
    return tuple(sorted(nodes))


def _highest_difficulty_level(payload: dict[str, Any], node: int) -> dict[str, Any]:
    fields = [_field_for_node(node)]
    if node in (1, 3):
        fields.append("boss_monster_id")
    levels: list[dict[str, Any]] = []
    for field in fields:
        levels = [
            level
            for level in payload.get("level", [])
            if isinstance(level, dict) and field in level
        ]
        if levels:
            break
    if not levels:
        raise ValueError(f"末日数据中未找到节点 {node}。")
    return max(levels, key=lambda level: int(level.get("id", 0)))


def _phase_ids(level: dict[str, Any], node: int) -> tuple[int, ...]:
    phase_ids: list[int] = []
    if node == 1 and "boss_monster_id1" in level:
        suffix = 1
        while f"boss_monster_id{suffix}" in level:
            value = level[f"boss_monster_id{suffix}"]
            if isinstance(value, int):
                phase_ids.append(value)
            suffix += 1
    else:
        value = level.get(_field_for_node(node))
        if value is None and node in (1, 3):
            value = level.get("boss_monster_id")
        if isinstance(value, int):
            phase_ids.append(value)
    return tuple(phase_ids)


def _stage_level(level: dict[str, Any], node: int) -> int:
    event_key = f"event_id_list{node}"
    events = level.get(event_key) or level.get("event_id_list") or []
    values = [event.get("level", 0) for event in events if isinstance(event, dict)]
    return max((int(value) for value in values), default=0)


def _format_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_percent(value: Any) -> str:
    if isinstance(value, (int, float)) and abs(value) <= 1:
        value = value * 100
    formatted = f"{value:g}" if isinstance(value, float) else str(value)
    return f"{formatted}%"


def format_effect(text: str, params: list[Any]) -> str:
    def replace_percent(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        return _format_percent(params[index]) if index < len(params) else match.group(0)

    def replace_number(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        return _format_number(params[index]) if index < len(params) else match.group(0)

    text = re.sub(r"#(\d+)\[i\]%", replace_percent, text)
    text = re.sub(r"#(\d+)\[i\]", replace_number, text)
    return re.sub(r"</?[^>]+>", "", text)


def _load_monster(data_root: Path, version: str, monster_id: int) -> dict[str, Any]:
    path = data_root / version / "zh" / "monster" / f"{_monster_template_id(monster_id)}.json"
    return _load_json(path)


def _phase_count(
    payload: dict[str, Any],
    node: int,
    phase_ids: tuple[int, ...],
    monster: dict[str, Any] | None = None,
) -> int:
    if node == 3 and isinstance(monster, dict):
        monster_phases = monster.get("phase_list")
        if isinstance(monster_phases, list) and monster_phases:
            return len(monster_phases)
    config = payload.get(f"boss_monster_config{node}")
    if not isinstance(config, dict) and node in (1, 3):
        config = payload.get("boss_monster_config")
    phases = config.get("phase_list") if isinstance(config, dict) else None
    if isinstance(phases, list) and phases:
        return len(phases)
    return len(phase_ids)


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return ()


def _previous_elite_ratio(
    version: str,
    resource_id: str,
    node: int,
    monster_id: int,
    stage_level: int,
    data_root: Path,
    scaling: EnemyScaling,
) -> float | None:
    """Find a matching ratio in an earlier local record when an id is absent."""
    family = ".".join(version.split(".")[:2])
    current_key = _version_key(version)
    candidates = sorted(
        (
            path.name
            for path in data_root.iterdir()
            if path.is_dir()
            and path.name != "config"
            and ".".join(path.name.split(".")[:2]) == family
            and _version_key(path.name) < current_key
        ),
        key=_version_key,
        reverse=True,
    )
    for candidate in candidates:
        path = data_root / candidate / "zh" / "boss" / f"{resource_id}.json"
        try:
            payload = _load_json(path)
            level_data = _highest_difficulty_level(payload, node)
            phase_ids = _phase_ids(level_data, node)
            stage = _stage_level(level_data, node)
            events = level_data.get(f"event_id_list{node}")
            if not isinstance(events, list) or not events:
                events = level_data.get("event_id_list") if node in (1, 3) else []
            event = next((item for item in events if isinstance(item, dict)), {})
            group = int(event.get("elite_group", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if (
            stage == stage_level
            and phase_ids
            and phase_ids[0] == monster_id
            and group in scaling.elite_hp
        ):
            return scaling.elite_hp[group]
    return None


def load_boss(
    version: str,
    resource_id: str,
    node: int,
    data_root: Path = DATA_DIR,
) -> BossView:
    boss_path = data_root / version / "zh" / "boss" / f"{resource_id}.json"
    payload = _load_json(boss_path)
    level_data = _highest_difficulty_level(payload, node)
    phase_ids = _phase_ids(level_data, node)
    if not phase_ids:
        raise ValueError(f"末日节点 {node} 未找到敌人数据。")

    monster = _load_monster(data_root, version, phase_ids[0])
    base_hp = float(monster.get("hp_base", 0))
    child = next(
        (
            item
            for item in monster.get("child", [])
            if isinstance(item, dict) and item.get("id") == phase_ids[0]
        ),
        {},
    )
    hp_ratio = float(child.get("hp_modify_ratio", 1))
    events = level_data.get(f"event_id_list{node}")
    if not isinstance(events, list) or not events:
        events = level_data.get("event_id_list") if node in (1, 3) else []
    event = next((item for item in events if isinstance(item, dict)), {})
    hard_level_group = int(event.get("hard_level_group", child.get("hard_level_group", 1)))
    elite_group = event.get("elite_group", child.get("elite_group", 1))
    scaling = load_enemy_scaling(data_root)
    stage_level = _stage_level(level_data, node)
    elite_ratio = scaling.elite_hp.get(int(elite_group))
    if elite_ratio is None:
        elite_ratio = _previous_elite_ratio(
            version,
            resource_id,
            node,
            phase_ids[0],
            stage_level,
            data_root,
            scaling,
        )
    if elite_ratio is None:
        raise ValueError(f"未找到 EliteGroup {elite_group} 的生命值系数。")
    buffs = tuple(
        BossBuff(
            name=str(item.get("name", "")),
            description=format_effect(str(item.get("desc", "")), item.get("param", [])),
        )
        for item in payload.get(f"buff_list{node}", [])
        if isinstance(item, dict)
    )
    return BossView(
        version=version,
        node=node,
        level=stage_level,
        name=str(monster.get("name", "未知敌人")),
        hp=calculate_hp(
            scaling,
            base_hp,
            hp_ratio,
            hard_level_group,
            stage_level,
            int(elite_group),
            hp_multiplier=elite_ratio - 1,
            round_up=monster.get("rank") == "LittleBoss",
        ),
        phases=_phase_count(level_data, node, phase_ids, monster),
        buffs=buffs,
    )

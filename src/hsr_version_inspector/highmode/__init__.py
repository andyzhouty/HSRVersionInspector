from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..boss import BossBuff, _load_json, format_effect
from ..paths import DATA_DIR
from .enemies import _build_view
from .models import HighModeEnemy, HighModeView, HighModeWave, MazeView

__all__ = [
    "HighModeEnemy",
    "HighModeView",
    "HighModeWave",
    "MazeView",
    "available_maze_nodes",
    "available_story_nodes",
    "load_maze",
    "load_peak",
    "load_story",
]


def highest_hp_enemy_name(view: HighModeView) -> str:
    """Return the name of the enemy with the highest individual HP."""
    enemies = [enemy for wave in view.waves for enemy in wave.enemies]
    if not enemies:
        return view.title
    enemy = max(
        enemies,
        key=lambda item: max(item.phase_hps or (item.hp,)),
    )
    return enemy.name


def _format_buffs(items: Any) -> tuple[BossBuff, ...]:
    if not isinstance(items, list):
        return ()
    return tuple(
        BossBuff(
            name=str(item.get("name", "")),
            description=format_effect(str(item.get("desc", "")), item.get("param", [])),
        )
        for item in items
        if isinstance(item, dict) and item.get("name")
    )


def _event(level: dict[str, Any], key: str = "event_id_list") -> dict[str, Any]:
    events = level.get(key) or []
    if not isinstance(events, list) or not events or not isinstance(events[0], dict):
        raise ValueError(f"在 {key} 中未找到关卡事件。")
    return events[0]


def _maze_entries(payload: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, list):
        raise ValueError("混沌数据应为 JSON 数组。")
    return tuple(
        item
        for item in payload
        if isinstance(item, dict)
        and item.get("name")
        and any(
            isinstance(item.get(key), list) and item.get(key)
            for key in ("event_id_list1", "event_id_list2", "event_id_list")
        )
    )


def _maze_primary_entry(payload: Any) -> dict[str, Any]:
    entries = _maze_entries(payload)
    if not entries:
        raise ValueError("混沌数据中未找到可展示的关卡。")
    def level_key(item: dict[str, Any]) -> tuple[int, int]:
        levels = [
            int(event.get("level", 0))
            for key in ("event_id_list1", "event_id_list2")
            for event in item.get(key, ())
            if isinstance(event, dict)
        ]
        return max(levels, default=0), int(item.get("id", 0))
    return max(entries, key=level_key)


def _maze_layer_sources(
    payload: Any,
) -> tuple[tuple[dict[str, Any], str], ...]:
    """Return the three nodes belonging to the highest maze layer.

    The numbered events are stored on the named entry (nodes 1 and 2).  The
    third event is a separate unnamed entry linked by ``pre_id``.
    """
    primary = _maze_primary_entry(payload)

    primary_id = primary.get("id")
    related = next(
        (
            item
            for item in payload
            if isinstance(item, dict)
            and str(item.get("pre_id")) == str(primary_id)
            and isinstance(item.get("event_id_list"), list)
            and item.get("event_id_list")
        ),
        None,
    )
    sources: list[tuple[dict[str, Any], str]] = []
    for key in ("event_id_list1", "event_id_list2"):
        if isinstance(primary.get(key), list) and primary.get(key):
            sources.append((primary, key))
    if related is not None:
        sources.append((related, "event_id_list"))
    elif isinstance(primary.get("event_id_list"), list) and primary.get("event_id_list"):
        sources.append((primary, "event_id_list"))
    return tuple(sources)


def available_maze_nodes(
    version: str,
    resource_id: str,
    data_root: Path = DATA_DIR,
) -> tuple[int, ...]:
    payload = json.loads(
        (data_root / version / "zh" / "maze" / f"{resource_id}.json").read_text(
            encoding="utf-8"
        )
    )
    return tuple(range(1, len(_maze_layer_sources(payload)) + 1))


def available_story_nodes(
    version: str,
    resource_id: str,
    data_root: Path = DATA_DIR,
) -> tuple[int, ...]:
    payload = _load_json(data_root / version / "zh" / "story" / f"{resource_id}.json")
    nodes: set[int] = set()
    has_default_node = False
    for level in payload.get("level", []):
        if not isinstance(level, dict):
            continue
        for key in level:
            match = re.fullmatch(r"event_id_list(\d*)", str(key))
            if match:
                if match.group(1):
                    nodes.add(int(match.group(1)))
                else:
                    has_default_node = True
    if has_default_node:
        nodes.add(3 if nodes else 1)
    return tuple(sorted(nodes))


def load_peak(
    version: str,
    resource_id: str,
    kind: str,
    node: int | None = None,
    data_root: Path = DATA_DIR,
) -> HighModeView:
    path = data_root / version / "zh" / "peak" / f"{resource_id}.json"
    payload = _load_json(path)

    if kind == "knight":
        if node is None or node not in (1, 2, 3):
            raise ValueError("骑士节点必须是 1、2 或 3。")
        levels = payload.get("pre_level", [])
        if not isinstance(levels, list) or len(levels) < node:
            raise ValueError(f"异相数据中未找到骑士 {node}。")
        level_data = levels[node - 1]
        event = _event(level_data)
        buffs = _format_buffs(level_data.get("tag_list"))
        return _build_view(
            version,
            str(level_data.get("name", f"骑士（{node}）")),
            level_data,
            event,
            buffs,
            level_data.get("damage_type"),
            data_root,
            wave_profiles=tuple(
                item
                for item in level_data.get("infinite_list", {}).values()
                if isinstance(item, dict)
            ),
        )

    if kind not in ("king", "hard-king"):
        raise ValueError(f"不支持的异相模式：{kind}。")
    boss_level = payload.get("boss_level")
    if not isinstance(boss_level, dict):
        raise ValueError("异相数据不包含王棋等级。")
    config = payload.get("boss_config")
    if not isinstance(config, dict):
        raise ValueError("绝境配置无效。")
    level_data = config if kind == "hard-king" else boss_level
    event = _event(level_data)
    buffs = _format_buffs(level_data.get("tag_list"))
    season_buffs = _format_buffs(config.get("buff_list"))
    title = str(level_data.get("name", "王棋"))
    if kind == "hard-king":
        title = str(config.get("hard_name", "绝境"))
    return _build_view(
        version,
        title,
        level_data,
        event,
        buffs,
        boss_level.get("damage_type"),
        data_root,
        wave_profiles=tuple(
            item
            for item in level_data.get("infinite_list", {}).values()
            if isinstance(item, dict)
        ),
        season_buffs=season_buffs,
    )


def load_story(
    version: str,
    resource_id: str,
    node: int,
    data_root: Path = DATA_DIR,
) -> HighModeView:
    path = data_root / version / "zh" / "story" / f"{resource_id}.json"
    payload = _load_json(path)
    event_key = f"event_id_list{node}"
    fallback_event_key = "event_id_list" if node in (1, 3) else None
    candidates = [
        level
        for level in payload.get("level", [])
        if isinstance(level, dict)
        and level.get(event_key)
    ]
    if not candidates and fallback_event_key:
        candidates = [
            level
            for level in payload.get("level", [])
            if isinstance(level, dict) and level.get(fallback_event_key)
        ]
    if not candidates:
        raise ValueError(f"虚构数据中未找到节点 {node}。")

    def event_key_for(level: dict[str, Any]) -> str:
        if level.get(event_key):
            return event_key
        if fallback_event_key and level.get(fallback_event_key):
            return fallback_event_key
        raise ValueError(f"虚构数据中未找到节点 {node}。")

    level_data = max(
        candidates,
        key=lambda level: (
            int(_event(level, event_key_for(level)).get("level", 0)),
            int(level.get("id", 0)),
        ),
    )
    selected_event_key = event_key_for(level_data)
    event = _event(level_data, selected_event_key)
    infinite_key = f"infinite_list{node}"
    if node in (1, 3) and not isinstance(level_data.get(infinite_key), dict):
        infinite_key = "infinite_list"
    name = level_data.get("name")
    story_effects: list[Any] = []
    for key in ("option", "sub_option"):
        items = payload.get(key)
        if isinstance(items, list):
            story_effects.extend(items)
    story_buffs = _format_buffs(story_effects) or _format_buffs(payload.get("buff"))
    view = _build_view(
        version,
        str(name) if name else f"虚构节点 {node}",
        level_data,
        event,
        (),
        level_data.get(f"damage_type{node}", level_data.get("damage_type")),
        data_root,
        infinite_key=infinite_key,
        wave_profiles=tuple(
            item
            for item in level_data.get(infinite_key, {}).values()
            if isinstance(item, dict)
        ),
        use_profile_hp_multiplier=True,
        season_buffs=story_buffs,
    )
    return replace(view, title=highest_hp_enemy_name(view))


def load_maze(
    version: str,
    resource_id: str,
    node: int,
    data_root: Path = DATA_DIR,
) -> MazeView:
    path = data_root / version / "zh" / "maze" / f"{resource_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = _maze_layer_sources(payload)
    if node < 1 or node > len(sources):
        raise ValueError(f"混沌节点必须是 1 到 {len(sources)}。")

    primary = _maze_primary_entry(payload)
    item, event_key = sources[node - 1]
    name = str(primary["name"])
    buffs = (
        BossBuff(
            name=str(primary.get("group_name") or "混沌效果"),
            description=format_effect(
                str(primary.get("desc", "")),
                primary.get("param", []),
            ),
        ),
    ) if primary.get("desc") else ()

    event = _event(item, event_key)
    if event_key == "event_id_list1":
        elements = item.get("damage_type1", item.get("damage_type", []))
    elif event_key == "event_id_list2":
        elements = item.get("damage_type2", item.get("damage_type", []))
    else:
        elements = item.get("damage_type", [])
    part = _build_view(
        version,
        f"节点 {node}",
        item,
        event,
        buffs,
        elements,
        data_root,
        infinite_scaling=False,
    )
    part = replace(part, title=highest_hp_enemy_name(part))
    return MazeView(version, node, name, (part,))

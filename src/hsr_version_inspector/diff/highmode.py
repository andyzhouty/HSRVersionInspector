"""High-mode comparison domain logic."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..boss import available_boss_nodes, load_boss
from ..data import VersionRecord
from ..highmode import (
    HighModeView,
    available_maze_nodes,
    load_maze,
    load_peak,
    load_story,
)
from ..paths import DATA_DIR
from .common import (
    mode_label,
    read_json,
    resource_ids,
    resource_path,
    validate_request,
)
from .models import HighModeChange, HighModeDiffReport, HighModeSectionDiff


def _effect_map(view: HighModeView) -> dict[tuple[str, str], str]:
    effects: dict[tuple[str, str], str] = {}
    for scope, buffs in (("Season", view.season_buffs), ("Stage", view.buffs)):
        for buff in buffs:
            effects[(scope, buff.name)] = buff.description
    return effects


def _hp_map(view: HighModeView) -> dict[tuple[int, str], str]:
    values: dict[tuple[int, str], str] = {}
    for wave in view.waves:
        for enemy in wave.enemies:
            phase_hps = enemy.phase_hps or (enemy.hp,)
            if len(phase_hps) == 1:
                hp = f"HP {phase_hps[0]:,}"
            elif len(set(phase_hps)) == 1:
                hp = f"HP {phase_hps[0]:,} × {len(phase_hps)}"
            else:
                hp = " / ".join(
                    f"第{phase}阶段：{value:,}" for phase, value in enumerate(phase_hps, 1)
                )
            count = f"×{enemy.count}；" if enemy.count > 1 else ""
            values[(wave.number, enemy.name)] = f"{count}{hp}"
    return values


def _view_changes(before: HighModeView, after: HighModeView) -> tuple[HighModeChange, ...]:
    changes: list[HighModeChange] = []

    def add(
        category: str,
        label: str,
        old: str | None,
        new: str | None,
        *,
        wave: int | None = None,
        subject: str | None = None,
    ) -> None:
        if old != new:
            kind = "added" if old is None else "removed" if new is None else "changed"
            changes.append(HighModeChange(category, label, old, new, kind, wave, subject))

    add("metadata", "Title", before.title, after.title)
    add("metadata", "Level", str(before.level), str(after.level))

    before_effects = _effect_map(before)
    after_effects = _effect_map(after)
    for key in sorted(set(before_effects) | set(after_effects)):
        scope, name = key
        add(
            "effects",
            f"{scope}: {name}",
            before_effects.get(key),
            after_effects.get(key),
            subject=name,
        )

    before_hp = _hp_map(before)
    after_hp = _hp_map(after)
    for key in sorted(set(before_hp) | set(after_hp)):
        wave, name = key
        add(
            "hp",
            f"Wave {wave}: {name}",
            before_hp.get(key),
            after_hp.get(key),
            wave=wave,
            subject=name,
        )
    return tuple(changes)


def _maze_resource(record: VersionRecord) -> str:
    resources = resource_ids(record, "maze")
    if len(resources) != 1:
        raise ValueError("混沌比较需要恰好一个混沌资源。")
    return resources[0]


def compare_maze_versions(
    version_one: str,
    version_two: str,
    node: int,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> HighModeDiffReport:
    if node < 1:
        raise ValueError("混沌比较需要提供正整数节点，例如 maze 1。")
    validate_request(record_one, record_two, version_one, version_two, "maze")
    resource_one = _maze_resource(record_one)
    resource_two = _maze_resource(record_two)
    nodes_one = available_maze_nodes(version_one, resource_one, data_root)
    nodes_two = available_maze_nodes(version_two, resource_two, data_root)
    if nodes_one != nodes_two:
        raise ValueError("两个版本必须拥有相同的混沌节点列表。")
    if node not in nodes_one:
        raise ValueError(f"混沌节点必须是 {nodes_one[0]} 到 {nodes_one[-1]}。")
    before = load_maze(version_one, resource_one, node, data_root).parts[0]
    after = load_maze(version_two, resource_two, node, data_root).parts[0]
    changes = _view_changes(before, after)
    return HighModeDiffReport(
        version_one,
        version_two,
        "maze",
        (HighModeSectionDiff(f"Maze {node}", "changed" if changes else "unchanged", changes),),
    )


def compare_all_maze_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[HighModeDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "maze")
    resource_one = _maze_resource(record_one)
    resource_two = _maze_resource(record_two)
    nodes_one = available_maze_nodes(version_one, resource_one, data_root)
    nodes_two = available_maze_nodes(version_two, resource_two, data_root)
    if nodes_one != nodes_two:
        raise ValueError("两个版本必须拥有相同的混沌节点列表。")
    return tuple(
        compare_maze_versions(
            version_one,
            version_two,
            node,
            record_one,
            record_two,
            data_root,
        )
        for node in nodes_one
    )


def _boss_effect_map(view: Any) -> dict[str, str]:
    return {buff.name: buff.description for buff in view.buffs}


def _boss_hp_text(view: Any) -> str:
    suffix = f" × {view.phases}" if view.phases > 1 else ""
    return f"HP {view.hp:,}{suffix}"


def _boss_changes(before: Any, after: Any) -> tuple[HighModeChange, ...]:
    changes: list[HighModeChange] = []

    def add(label: str, old: str | None, new: str | None) -> None:
        if old != new:
            kind = "added" if old is None else "removed" if new is None else "changed"
            changes.append(HighModeChange("metadata", label, old, new, kind, subject=label))

    add("名称", before.name, after.name)
    add("等级", str(before.level), str(after.level))
    add("阶段数", str(before.phases), str(after.phases))

    before_effects = _boss_effect_map(before)
    after_effects = _boss_effect_map(after)
    for name in sorted(set(before_effects) | set(after_effects)):
        old = before_effects.get(name)
        new = after_effects.get(name)
        if old != new:
            kind = "added" if old is None else "removed" if new is None else "changed"
            changes.append(HighModeChange("effects", name, old, new, kind, subject=name))

    old_hp = _boss_hp_text(before)
    new_hp = _boss_hp_text(after)
    if old_hp != new_hp:
        name = after.name or before.name
        changes.append(
            HighModeChange(
                "hp",
                f"Boss: {name}",
                old_hp,
                new_hp,
                "changed",
                wave=0,
                subject=name,
            )
        )
    return tuple(changes)


def compare_boss_versions(
    version_one: str,
    version_two: str,
    node: int,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
    *,
    load_boss_fn=load_boss,
) -> HighModeDiffReport:
    if node < 1:
        raise ValueError("末日比较需要提供正整数节点，例如 boss 1。")
    validate_request(record_one, record_two, version_one, version_two, "boss")
    resource_one = resource_ids(record_one, "boss")
    resource_two = resource_ids(record_two, "boss")
    if len(resource_one) != 1 or len(resource_two) != 1:
        raise ValueError("末日比较需要每个版本恰好一个末日资源。")
    before = load_boss_fn(version_one, resource_one[0], node, data_root)
    after = load_boss_fn(version_two, resource_two[0], node, data_root)
    changes = _boss_changes(before, after)
    return HighModeDiffReport(
        version_one,
        version_two,
        "boss",
        (HighModeSectionDiff(f"Boss {node}", "changed" if changes else "unchanged", changes),),
    )


def compare_all_boss_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
    *,
    available_boss_nodes_fn=available_boss_nodes,
    load_boss_fn=load_boss,
) -> tuple[HighModeDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "boss")
    ids_one = resource_ids(record_one, "boss")
    ids_two = resource_ids(record_two, "boss")
    if len(ids_one) != 1 or len(ids_two) != 1:
        raise ValueError("末日比较需要每个版本恰好一个末日资源。")
    nodes_one = available_boss_nodes_fn(version_one, ids_one[0], data_root)
    nodes_two = available_boss_nodes_fn(version_two, ids_two[0], data_root)
    if nodes_one != nodes_two:
        raise ValueError("两个版本必须拥有相同的末日节点列表。")
    return tuple(
        compare_boss_versions(
            version_one,
            version_two,
            node,
            record_one,
            record_two,
            data_root,
            load_boss_fn=load_boss_fn,
        )
        for node in nodes_one
    )


def _peak_resource(record: VersionRecord) -> str:
    resources = resource_ids(record, "peak")
    if len(resources) != 1:
        raise ValueError("异相比对需要恰好一个异相资源。")
    return resources[0]


def _story_resource(record: VersionRecord) -> str:
    resources = resource_ids(record, "story")
    if len(resources) != 1:
        raise ValueError("虚构比较需要恰好一个虚构资源。")
    return resources[0]


def _story_nodes(
    version: str,
    record: VersionRecord,
    data_root: Path,
) -> tuple[int, ...]:
    payload = read_json(
        resource_path(data_root, version, "story", _story_resource(record))
    )
    if not isinstance(payload, dict):
        raise ValueError(f"版本 {version} 的虚构数据无效。")
    nodes: set[int] = set()
    has_default_node = False
    levels = payload.get("level")
    if isinstance(levels, list):
        for level in levels:
            if not isinstance(level, dict):
                continue
            for key in level:
                match = re.fullmatch(r"event_id_list(\d+)", str(key))
                if match:
                    nodes.add(int(match.group(1)))
                elif key == "event_id_list":
                    has_default_node = True
    if has_default_node:
        nodes.add(3 if nodes else 1)
    if not nodes:
        raise ValueError(f"版本 {version} 的虚构数据不包含可比较的节点。")
    return tuple(sorted(nodes))


def compare_highmode_versions(
    version_one: str,
    version_two: str,
    mode: str,
    node: int | None,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> HighModeDiffReport:
    if mode == "peak" or (mode == "knight" and node is None):
        if mode == "peak" and node is not None:
            raise ValueError("异相比对不接受节点参数，会比较所有异相分段。")
        validate_request(record_one, record_two, version_one, version_two, "peak")
        if mode == "knight":
            sections = (
                ("Knight 1", "knight", 1),
                ("Knight 2", "knight", 2),
                ("Knight 3", "knight", 3),
            )
        else:
            sections = (
                ("Knight 1", "knight", 1),
                ("Knight 2", "knight", 2),
                ("Knight 3", "knight", 3),
                ("King", "king", None),
                ("Hard-king", "hard-king", None),
            )
        resource_one = _peak_resource(record_one)
        resource_two = _peak_resource(record_two)
        section_reports = [
            _compare_peak_section(
                name,
                version_one,
                version_two,
                resource_one,
                resource_two,
                kind,
                section_node,
                data_root,
            )
            for name, kind, section_node in sections
        ]
        return HighModeDiffReport(version_one, version_two, mode, tuple(section_reports))

    if mode == "story":
        if node is None or node < 1:
            raise ValueError("虚构比较需要节点编号，例如 story 1。")
        validate_request(record_one, record_two, version_one, version_two, mode)
        before = load_story(version_one, _story_resource(record_one), node, data_root)
        after = load_story(version_two, _story_resource(record_two), node, data_root)
        changes = _view_changes(before, after)
        return HighModeDiffReport(
            version_one,
            version_two,
            f"story {node}",
            (HighModeSectionDiff(f"Story {node}", "changed" if changes else "unchanged", changes),),
        )

    if mode not in {"knight", "king", "hard-king"}:
        raise ValueError(f"高难度 diff 不支持模式 {mode!r}。")
    validate_request(record_one, record_two, version_one, version_two, "peak")
    resource_one = _peak_resource(record_one)
    resource_two = _peak_resource(record_two)
    if mode == "knight":
        if node not in (1, 2, 3):
            raise ValueError("骑士比较的节点必须是 1、2 或 3。")
        name = f"Knight {node}"
    else:
        if node is not None:
            raise ValueError(f"{mode_label(mode)}比较不接受节点参数。")
        name = "King" if mode == "king" else "Hard-king"
    section = _compare_peak_section(
        name,
        version_one,
        version_two,
        resource_one,
        resource_two,
        mode,
        node,
        data_root,
    )
    return HighModeDiffReport(version_one, version_two, mode, (section,))


def _compare_peak_section(
    name: str,
    version_one: str,
    version_two: str,
    resource_one: str,
    resource_two: str,
    kind: str,
    node: int | None,
    data_root: Path,
) -> HighModeSectionDiff:
    before = load_peak(version_one, resource_one, kind, node, data_root)
    after = load_peak(version_two, resource_two, kind, node, data_root)
    changes = _view_changes(before, after)
    return HighModeSectionDiff(name, "changed" if changes else "unchanged", changes)


def compare_all_story_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[HighModeDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "story")
    nodes_one = _story_nodes(version_one, record_one, data_root)
    nodes_two = _story_nodes(version_two, record_two, data_root)
    if nodes_one != nodes_two:
        raise ValueError("两个版本必须拥有相同的虚构节点列表。")
    return tuple(
        compare_highmode_versions(
            version_one,
            version_two,
            "story",
            node,
            record_one,
            record_two,
            data_root,
        )
        for node in nodes_one
    )

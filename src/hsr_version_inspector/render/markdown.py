"""Markdown renderer for catalog, show, query, and diff results."""

from __future__ import annotations

import re
from typing import Any

from ..boss import BossBuff, BossView
from ..character import (
    CharacterSkill,
    CharacterText,
    CharacterView,
    group_skill_entries,
    skill_entry_title,
    skill_group_title,
)
from ..data import VersionRecord
from ..diff import (
    CharacterChange,
    CharacterDiffReport,
    DiffReport,
    HighModeChange,
    HighModeDiffReport,
    LightConeChange,
    LightConeDiffReport,
    character_change_subject,
    format_name_change,
    format_value,
    highmode_change_subject,
    highmode_change_wave,
    is_missing,
)
from ..highmode import HighModeView
from ..lightcone import LightConeView
from ..output.diff_markup import (
    markdown_lightcone_text_markup,
    markdown_shared_text_arrow_markup,
    markdown_shared_text_markup,
    rich_text_diff_markup,
)
from ..output.labels import STATUS_LABELS, element_label, mode_label
from ..output.text import (
    markdown_enemy_count_text,
    markdown_table,
    markdown_text,
    rich_markup_to_markdown,
)


def _highmode_section_label(name: str) -> str:
    label = {
        "Knight 1": "骑士 1",
        "Knight 2": "骑士 2",
        "Knight 3": "骑士 3",
        "King": "王棋",
        "Hard-king": "绝境",
    }.get(name)
    if label:
        return label
    match = re.fullmatch(r"Story (\d+)", name)
    if match:
        return f"虚构节点 {match.group(1)}"
    match = re.fullmatch(r"Maze (\d+)", name)
    if match:
        return f"混沌节点 {match.group(1)}"
    match = re.fullmatch(r"Boss (\d+)", name)
    return f"末日节点 {match.group(1)}" if match else name


def _highmode_metadata_label(label: str) -> str:
    return {"Title": "名称", "Level": "等级"}.get(label, label)


def _highmode_change_sort_key(change: HighModeChange) -> tuple[int, str]:
    priority = {"removed": 0, "added": 1, "changed": 2}
    return priority.get(change.kind, 3), change.label


def _change_sort_key(change: Any) -> tuple[int, str]:
    priority = {"removed": 0, "added": 1, "changed": 2}
    return priority.get(change.kind, 3), change.label


def catalog(catalog: tuple[VersionRecord, ...]) -> list[str]:
    lines = ["# 星穹铁道版本检查器", ""]
    lines.extend(
        markdown_table(
            ("版本组", "版本数", "角色", "光锥", "虚构", "末日"),
            [
                (
                    record.name,
                    len(record.versions),
                    len(record.character),
                    len(record.lightcone),
                    record.story or "-",
                    record.boss or "-",
                )
                for record in catalog
            ],
        )
    )
    lines.extend(
        [
            "",
            f"共 {len(catalog)} 个版本组，追踪 "
            f"{sum(record.content_count for record in catalog)} 个数据项。",
        ]
    )
    return lines


def buffs(lines: list[str], title: str, entries: tuple) -> None:
    if not entries:
        return
    lines.extend(["", f"## {markdown_text(title)}"])
    for entry in entries:
        lines.extend(["", f"### {markdown_text(entry.name)}", markdown_text(entry.description)])


def character(view: CharacterView, verbose: bool) -> list[str]:
    lines = [f"# {markdown_text(view.name)}", ""]
    summary: list[tuple[str, object]] = [
        ("等级", f"{view.level}级"),
        ("角色编号", view.character_id),
        ("命途", view.path),
    ]
    if view.base_stats:
        summary.extend(
            [
                ("基础生命值", view.base_stats.hp),
                ("基础攻击力", view.base_stats.attack),
                ("基础防御力", view.base_stats.defence),
                ("基础速度", view.base_stats.speed),
            ]
        )
    lines.extend(markdown_table(("属性", "数值"), summary))

    def add_skills(title: str, entries: tuple[CharacterSkill, ...]) -> None:
        if not entries:
            return
        lines.extend(["", f"## {markdown_text(title)}"])
        for group in group_skill_entries(entries):
            lines.extend(["", f"### {markdown_text(skill_group_title(group))}"])
            for index, entry in enumerate(group):
                if index:
                    lines.extend(["", "---"])
                lines.extend(
                    [
                        "",
                        f"#### {markdown_text(skill_entry_title(group, entry))}",
                        markdown_text(entry.description),
                    ]
                )

    def add_texts(title: str, entries: tuple[CharacterText, ...]) -> None:
        if not entries:
            return
        lines.extend(["", f"## {markdown_text(title)}"])
        for entry in entries:
            lines.extend(["", f"### {markdown_text(entry.name)}", markdown_text(entry.description)])

    add_skills("技能", view.skills)
    if view.memosprite_name:
        add_skills(f"忆灵 · {view.memosprite_name}", view.memosprite_skills)
    add_texts("行迹", view.traces)
    if view.trace_stats:
        lines.extend(["", "### 行迹属性"])
        lines.extend(
            markdown_table(
                tuple(stat.name for stat in view.trace_stats),
                [tuple(stat.description for stat in view.trace_stats)],
            )
        )
    if verbose:
        add_texts("特殊效果", view.special_effects)
    add_texts("星魂", view.eidolons)
    return lines


def lightcone(view: LightConeView) -> list[str]:
    lines = [f"# {markdown_text(view.name)}", ""]
    lines.extend(
        markdown_table(
            ("属性", "数值"),
            [
                ("等级", f"{view.level}级"),
                ("稀有度", f"{view.rarity}星"),
                ("命途", view.path),
                ("生命值", view.hp),
                ("攻击力", view.attack),
                ("防御力", view.defence),
                ("叠影", view.refinement),
            ],
        )
    )
    lines.extend(["", "## 光锥效果", "", f"### {markdown_text(view.refinement_name)}", markdown_text(view.description)])
    return lines


def boss(view: BossView, title: str | None) -> list[str]:
    lines = [f"# {markdown_text(title or view.name)}", ""]
    hp = f"{view.hp:,}" if view.phases <= 1 else f"{view.hp:,} × {view.phases}"
    lines.extend(
        markdown_table(
            ("属性", "数值"),
            [("首领", view.name), ("等级", f"{view.level}级"), ("生命值", hp)],
        )
    )
    buffs(lines, "增益效果", view.buffs)
    return lines


def highmode(
    view: HighModeView,
    title: str | None = None,
    stage_buffs: tuple[BossBuff, ...] | None = None,
    prelude_buffs: tuple[BossBuff, ...] | None = None,
) -> list[str]:
    lines: list[str] = []
    if prelude_buffs:
        buffs(lines, "虚构效果", prelude_buffs)
    lines.extend([f"# {markdown_text(title or view.title)}", ""])
    summary: list[tuple[str, object]] = [("等级", f"{view.level}级")]
    summary.append(("推荐元素", ", ".join(element_label(element) for element in view.recommended_elements) or "无"))
    if view.phases > 1:
        summary.append(("阶段数", view.phases))
    lines.extend(markdown_table(("属性", "数值"), summary))
    if prelude_buffs is None:
        buffs(lines, "赛季效果", view.season_buffs)
    buffs(lines, "关卡效果", view.buffs if stage_buffs is None else stage_buffs)
    lines.extend(["", "## 敌人波次"])
    for wave in view.waves:
        lines.extend(["", f"### 第 {wave.number} 波 · 等级 {wave.level}"])
        wave_phases = max((len(enemy.phase_hps) for enemy in wave.enemies), default=1)
        same_phase_hp = wave_phases > 1 and all(
            len(enemy.phase_hps) == wave_phases and len(set(enemy.phase_hps)) == 1
            for enemy in wave.enemies
        )
        if wave_phases > 1 and not same_phase_hp:
            headers = ("敌人", "数量", *tuple(f"P{phase}" for phase in range(1, wave_phases + 1)))
        else:
            headers = ("敌人", "数量", "生命值")
        rows: list[tuple[object, ...]] = []
        for enemy in wave.enemies:
            if same_phase_hp:
                hp_values: tuple[object, ...] = (f"{enemy.phase_hps[0]:,} × {wave_phases}",)
            elif wave_phases > 1:
                hp_values = tuple(f"{value:,}" for value in enemy.phase_hps[:wave_phases])
            else:
                hp_values = (f"{enemy.hp:,}",)
            rows.append((enemy.name, markdown_enemy_count_text(enemy.count), *hp_values))
        lines.extend(markdown_table(headers, rows))
    return lines


def character_change(change: CharacterChange) -> str:
    if change.kind == "added":
        return f"新增：{markdown_text(change.after or '')}"
    if change.kind == "removed":
        return f"删除：{markdown_text(change.before or '')}"
    return rich_markup_to_markdown(markdown_shared_text_markup(change.before or "", change.after or ""))


def base_change_value(change: CharacterChange | LightConeChange) -> str:
    if change.kind == "added":
        return f"新增：{markdown_text(change.after or '')}"
    if change.kind == "removed":
        return f"删除：{markdown_text(change.before or '')}"
    return f"~~{markdown_text(change.before or '')}~~ {markdown_text(change.after or '')}"


def lightcone_change(change: LightConeChange) -> str:
    if change.kind == "added":
        return f"新增：{markdown_text(change.after or '')}"
    if change.kind == "removed":
        return f"删除：{markdown_text(change.before or '')}"
    return rich_markup_to_markdown(markdown_lightcone_text_markup(change.before or "", change.after or ""))


def json_change(change: Any) -> str:
    if is_missing(change.before):
        return f"新增：{markdown_text(format_value(change.after))}"
    if is_missing(change.after):
        return f"删除：{markdown_text(format_value(change.before))}"
    return f"~~{markdown_text(format_value(change.before))}~~ {markdown_text(format_value(change.after))}"


def diff(report: DiffReport) -> list[str]:
    changed = report.changed_resources
    lines = ["# 数据差异", ""]
    lines.extend(markdown_table(("版本", "模式", "变更资源数"), [(f"{report.version_one} → {report.version_two}", mode_label(report.mode), len(changed))]))
    if not changed:
        lines.extend(["", "未发现变更。"])
        return lines
    lines.extend(["", "## 资源概览", ""])
    lines.extend(markdown_table(
        ("资源", "状态", "变更数"),
        [(resource.resource_id, STATUS_LABELS.get(resource.status, resource.status), resource.change_count) for resource in changed],
    ))
    for resource in changed:
        lines.extend(["", f"## {markdown_text(mode_label(report.mode))}/{resource.resource_id}.json"])
        lines.extend(markdown_table(
            ("路径", "变更"),
            [(markdown_text(change.path), json_change(change)) for change in resource.changes],
            markup_rows=True,
        ))
    return lines


def character_diff(report: CharacterDiffReport, verbose: bool) -> list[str]:
    sections = tuple(section for section in report.sections if verbose or section.name != "特殊效果")
    changed_sections = tuple(section for section in sections if section.status != "unchanged")
    lines = ["# 角色差异", ""]
    lines.extend(markdown_table(
        ("版本", "角色", "变更分类数"),
        [(f"{report.version_one} → {report.version_two}", markdown_text(format_name_change(report.name_one, report.name_two)), len(changed_sections))],
    ))
    if not changed_sections:
        lines.extend(["", "未发现变更。"])
        return lines
    lines.extend(["", "## 变更分类", ""])
    lines.extend(markdown_table(
        ("分类", "状态", "变更数"),
        [(section.name, STATUS_LABELS["changed"], len(section.changes)) for section in changed_sections],
    ))
    for section in changed_sections:
        lines.extend(["", f"## {markdown_text(section.name)}"])
        if section.name == "基础属性":
            lines.extend(markdown_table(
                tuple(markdown_text(change.label) for change in section.changes),
                [[base_change_value(change) for change in section.changes]],
                markup_rows=True,
            ))
            continue
        rows = [
            (markdown_text(character_change_subject(section.name, change)), character_change(change))
            for change in sorted(section.changes, key=_change_sort_key)
        ]
        lines.extend(markdown_table(("项目", "变更"), rows, markup_rows=True))
    return lines


def lightcone_diff(report: LightConeDiffReport) -> list[str]:
    changed_sections = tuple(section for section in report.sections if section.status != "unchanged")
    lines = ["# 光锥差异", ""]
    lines.extend(markdown_table(
        ("版本", "光锥", "变更分类数"),
        [(f"{report.version_one} → {report.version_two}", markdown_text(format_name_change(report.name_one, report.name_two)), len(changed_sections))],
    ))
    if not changed_sections:
        lines.extend(["", "未发现变更。"])
        return lines
    lines.extend(["", "## 变更分类", ""])
    lines.extend(markdown_table(
        ("分类", "状态", "变更数"),
        [(section.name, STATUS_LABELS["changed"], len(section.changes)) for section in changed_sections],
    ))
    for section in changed_sections:
        lines.extend(["", f"## {markdown_text(section.name)}"])
        rows = []
        for change in sorted(section.changes, key=_change_sort_key):
            value = base_change_value(change) if section.name == "基础属性" else lightcone_change(change)
            rows.append((markdown_text(change.label), value))
        lines.extend(markdown_table(("项目", "变更"), rows, markup_rows=True))
    return lines


def highmode_change(change: HighModeChange) -> str:
    if change.kind == "added":
        return f"新增：{markdown_text(change.after or '')}"
    if change.kind == "removed":
        return f"删除：{markdown_text(change.before or '')}"
    if change.category == "hp":
        return rich_markup_to_markdown(rich_text_diff_markup(change.before or "", change.after or "", arrow=True, whole=True))
    return rich_markup_to_markdown(markdown_shared_text_arrow_markup(change.before or "", change.after or ""))


def highmode_diff(report: HighModeDiffReport, include_header: bool = True) -> list[str]:
    lines: list[str] = []
    if include_header:
        lines.extend([f"# {markdown_text(mode_label(report.mode))}差异", ""])
        lines.extend(markdown_table(("版本", "模式"), [(f"{report.version_one} → {report.version_two}", mode_label(report.mode))]))
    if not report.changed_sections:
        lines.extend(["", "未发现变更。"])
        return lines
    for section in report.changed_sections:
        lines.extend(["", f"## {markdown_text(_highmode_section_label(section.name))}"])
        effect_changes = tuple(change for change in section.changes if change.category == "effects")
        if effect_changes:
            lines.extend(["", "### 关卡效果"])
            lines.extend(markdown_table(
                ("效果", "变更"),
                [(markdown_text(highmode_change_subject(change)), highmode_change(change)) for change in sorted(effect_changes, key=_highmode_change_sort_key)],
                markup_rows=True,
            ))
        hp_changes = tuple(change for change in section.changes if change.category == "hp")
        if hp_changes:
            lines.extend(["", "### 生命值"])
            waves: dict[int, list[HighModeChange]] = {}
            for change in hp_changes:
                waves.setdefault(highmode_change_wave(change) or 0, []).append(change)
            for wave, changes in waves.items():
                wave_label = "首领" if wave == 0 else f"第 {wave} 波"
                lines.extend(["", f"#### {wave_label}"])
                lines.extend(markdown_table(
                    ("敌人", "变更"),
                    [(markdown_text(highmode_change_subject(change)), highmode_change(change)) for change in sorted(changes, key=_highmode_change_sort_key)],
                    markup_rows=True,
                ))
        metadata_changes = tuple(change for change in section.changes if change.category == "metadata")
        if metadata_changes:
            lines.extend(["", "### 基本信息"])
            lines.extend(markdown_table(
                ("项目", "变更"),
                [(markdown_text(_highmode_metadata_label(change.label)), highmode_change(change)) for change in sorted(metadata_changes, key=_highmode_change_sort_key)],
                markup_rows=True,
            ))
    return lines

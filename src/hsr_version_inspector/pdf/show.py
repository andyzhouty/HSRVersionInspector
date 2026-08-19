"""Show-oriented PDF renderer mixin."""

from __future__ import annotations

from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import KeepTogether, Spacer

from ..boss import BossView
from ..character import (
    CharacterSkill,
    CharacterText,
    CharacterView,
    group_skill_entries,
)
from ..data import VersionRecord
from ..highmode import HighModeView
from ..lightcone import LightConeView
from .support import (
    CHARACTER_SPACING,
    FONT_BOLD,
    LIGHTCONE_SPACING,
    NODE_SPACING,
    RED,
    YELLOW,
    _element_label,
    _enemy_count_text,
    _paragraph,
)


class PdfShowMixin:
    def add_catalog(self: Any, catalog: tuple[VersionRecord, ...]) -> None:
        self.story.append(_paragraph("星穹铁道版本检查器", self.title))
        self._table(
            ("版本组", "版本数", "角色", "光锥", "虚构", "末日"),
            [
                (record.name, len(record.versions), len(record.character), len(record.lightcone), record.story or "-", record.boss or "-")
                for record in catalog
            ],
            [75, 60, 55, 55, 110, 110],
        )
        self.story.append(_paragraph(
            f"共 {len(catalog)} 个版本组，追踪 {sum(record.content_count for record in catalog)} 个数据项。",
            self.small,
        ))

    def add_error(self: Any, title: str, message: str) -> None:
        self._start_item()
        self.story.append(_paragraph(title, self.title))
        self._box("数据读取失败", message, RED)

    def add_boss(self: Any, view: BossView, title: str | None = None) -> None:
        has_previous_item = self.mode_item_count > 0
        self._start_item()
        if has_previous_item:
            self.story.append(Spacer(1, NODE_SPACING))
        content_width = self.width - 18
        hp = f"{view.hp:,}" if view.phases <= 1 else f"{view.hp:,} × {view.phases}"
        rows: list[list[Any]] = [
            [
                self._summary_table(
                    [("首领", view.name), ("等级", f"{view.level}级"), ("生命值", hp)],
                    [content_width / 3] * 3,
                )
            ]
        ]
        rows.extend(self._buff_rows(view.buffs))
        self._resource_table(title or view.name, rows)

    def _character_texts(self: Any, title: str, entries: tuple[CharacterText, ...]) -> None:
        if not entries:
            return
        self._heading(title)
        for entry in entries:
            self._box(entry.name, entry.description)

    def _skills(self: Any, title: str, entries: tuple[CharacterSkill, ...]) -> None:
        if not entries:
            return
        self._heading(title)
        for group in group_skill_entries(entries):
            self._skill_group_box(group)

    def add_character(self: Any, view: CharacterView, verbose: bool = False) -> None:
        has_previous_item = self.mode_item_count > 0
        self._start_item()
        if has_previous_item:
            self.story.append(Spacer(1, CHARACTER_SPACING))
        self._resource_heading(view.name)
        summary: list[tuple[object, ...]] = [
            ("角色编号", view.character_id),
            ("命途", view.path),
        ]
        if view.base_stats:
            summary.extend([
                ("基础生命值", view.base_stats.hp), ("基础攻击力", view.base_stats.attack),
                ("基础防御力", view.base_stats.defence), ("基础速度", view.base_stats.speed),
            ])
        self.story.append(self._summary_table(summary))
        self.story.append(Spacer(1, 6))
        self._skills("技能", view.skills)
        if view.memosprite_name:
            self._skills(f"忆灵 · {view.memosprite_name}", view.memosprite_skills)
        self._character_texts("行迹", view.traces)
        if view.trace_stats:
            heading = self._subheading_paragraph("行迹属性")
            table = self._table_flowable(
                tuple(stat.name for stat in view.trace_stats),
                [tuple(stat.description for stat in view.trace_stats)],
            )
            self.story.append(KeepTogether([heading, table, Spacer(1, 6)]))
        if verbose:
            self._character_texts("特殊效果", view.special_effects)
        self._character_texts("星魂", view.eidolons)

    def add_lightcone(self: Any, view: LightConeView) -> None:
        has_previous_item = self.mode_item_count > 0
        self._start_item()
        if has_previous_item:
            self.story.append(Spacer(1, LIGHTCONE_SPACING))
        content_width = self.width - 18
        rows: list[list[Any]] = [
            [
                self._summary_table(
                    [
                        ("稀有度", f"{view.rarity}星"),
                        ("命途", view.path),
                        ("生命值", view.hp),
                        ("攻击力", view.attack),
                        ("防御力", view.defence),
                    ],
                    [content_width / 5] * 5,
                )
            ],
            [
                [
                    _paragraph(view.refinement_name, self.box_title),
                    _paragraph(view.description, self.body),
                ]
            ],
        ]
        self._resource_table(view.name, rows)

    def add_highmode(
        self: Any,
        view: HighModeView,
        title: str | None = None,
        stage_buffs: tuple | None = None,
        prelude_buffs: tuple | None = None,
    ) -> None:
        has_previous_item = self.mode_item_count > 0
        self._start_item()
        if has_previous_item:
            self.story.append(Spacer(1, NODE_SPACING))
        if prelude_buffs:
            self._buffs("虚构效果", prelude_buffs)
        content_width = self.width - 18
        summary: list[tuple[object, ...]] = [
            (
                "等级",
                f"{view.level}级",
            ),
            (
                "推荐元素",
                "、".join(_element_label(element) for element in view.recommended_elements) or "无",
            ),
        ]
        if view.phases > 1:
            summary.append(("阶段数", view.phases))
        resource_rows: list[list[Any]] = [[
            self._summary_table(summary, [content_width / len(summary)] * len(summary))
        ]]
        if prelude_buffs is None:
            resource_rows.extend(self._buff_rows(view.season_buffs))
        resource_rows.extend(self._buff_rows(view.buffs if stage_buffs is None else stage_buffs))
        for wave in view.waves:
            phase_count = max((len(enemy.phase_hps) for enemy in wave.enemies), default=1)
            same_phase_hp = phase_count > 1 and all(
                len(enemy.phase_hps) == phase_count and len(set(enemy.phase_hps)) == 1
                for enemy in wave.enemies
            )
            headers = ("敌人", "数量", "生命值") if same_phase_hp or phase_count == 1 else (
                "敌人", "数量", *tuple(f"P{i}" for i in range(1, phase_count + 1))
            )
            wave_rows: list[tuple[object, ...]] = []
            for enemy in wave.enemies:
                count = _enemy_count_text(enemy.count)
                if same_phase_hp:
                    hp = f"{enemy.phase_hps[0]:,} × {phase_count}"
                    wave_rows.append((enemy.name, count, hp))
                elif phase_count > 1:
                    wave_rows.append((enemy.name, count, *[f"{hp:,}" for hp in enemy.phase_hps]))
                else:
                    wave_rows.append((enemy.name, count, f"{enemy.hp:,}"))
            widths = [content_width * 0.43, content_width * 0.12, (content_width * 0.45) / len(headers[2:])] if len(headers) > 3 else [content_width * 0.43, content_width * 0.12, content_width * 0.45]
            wave_heading_style = ParagraphStyle(
                "HviWaveHeading",
                parent=self.body,
                fontName=FONT_BOLD,
                fontSize=10.5,
                leading=14,
                textColor=YELLOW,
                spaceBefore=4,
                spaceAfter=3,
            )
            heading = _paragraph(f"第 {wave.number} 波 · 等级 {wave.level}", wave_heading_style)
            table = self._table_flowable(None, wave_rows, widths)
            resource_rows.append([heading])
            resource_rows.append([table])
        self._resource_table(title or view.title, resource_rows)

"""Diff-oriented PDF renderer mixin."""

from __future__ import annotations

from typing import Any

from reportlab.platypus import Spacer

from ..diff import (
    CharacterDiffReport,
    DiffReport,
    HighModeChange,
    HighModeDiffReport,
    LightConeDiffReport,
    character_change_subject,
    format_name_change,
    format_value,
    highmode_change_subject,
    highmode_change_wave,
    is_missing,
)
from .support import (
    CYAN,
    YELLOW,
    _changed_text,
    _diff_overview_highmode_label,
    _ensure_leading_strike,
    _inline_text,
    _markup_paragraph,
    _paragraph,
    _pdf_mode_label,
    _section_label,
    _terminal_diff_markup,
)


class PdfDiffMixin:
    def _json_change_body(self: Any, change: Any) -> str:
        if is_missing(change.before):
            return f'<font color="#198754">新增：{_inline_text(format_value(change.after))}</font>'
        if is_missing(change.after):
            return f'<font color="#c0392b">删除：{_inline_text(format_value(change.before))}</font>'
        return _ensure_leading_strike(
            f'<strike><font color="#c0392b">{_inline_text(format_value(change.before))}'
            f'</font></strike> → <font color="#198754">{_inline_text(format_value(change.after))}</font>'
        )

    def _status_change_row(
        self: Any,
        label: str,
        change: HighModeChange,
    ) -> tuple[str, str, str]:
        if change.kind == "added":
            color = "#198754"
            status = "新增"
            value = change.after or ""
        elif change.kind == "removed":
            color = "#c0392b"
            status = "删除"
            value = change.before or ""
        else:
            color = "#c27c0e"
            status = "更改"
            return (
                f'<font color="{color}">{_inline_text(label)}</font>',
                f'<font color="{color}">{status}</font>',
                _terminal_diff_markup(change.before or "", change.after or "", "status"),
            )
        return (
            f'<font color="{color}">{_inline_text(label)}</font>',
            f'<font color="{color}">{status}</font>',
            f'<font color="{color}">{_inline_text(value)}</font>',
        )

    def _change_body(
        self: Any,
        change: Any,
        numeric_only: bool = False,
        separator: str = "",
        whole: bool = False,
        style: str | None = None,
    ) -> str:
        if change.kind == "added":
            return f'<font color="#198754">新增：{_inline_text(change.after or "")}</font>'
        if change.kind == "removed":
            return f'<font color="#c0392b">删除：{_inline_text(change.before or "")}</font>'
        if whole:
            return _ensure_leading_strike(
                f'<strike><font color="#c0392b">{_inline_text(change.before or "")}</font></strike>'
                f'{separator}<font color="#198754">{_inline_text(change.after or "")}</font>'
            )
        if style is not None:
            return _terminal_diff_markup(change.before or "", change.after or "", style)
        return _changed_text(change.before or "", change.after or "", numeric_only, separator)

    def add_no_changes(self: Any) -> None:
        self.story.append(_paragraph("未发现变更。", self.body))

    def add_diff(self: Any, report: DiffReport) -> None:
        for resource in report.resources:
            self._register_diff_item(
                report.version_one,
                report.version_two,
                f"{_pdf_mode_label(report.mode)} · 资源 {resource.resource_id}",
                resource.change_count if resource.status != "unchanged" else 0,
            )
        changed = report.changed_resources
        if not changed:
            return
        self._start_item()
        self._ensure_diff_title(f"{_pdf_mode_label(report.mode)}差异")
        for resource in changed:
            self._resource_heading(f"资源 {resource.resource_id}")
            self.story.append(self._change_table([
                (change.path, self._json_change_body(change))
                for change in resource.changes
            ]))
            self.story.append(Spacer(1, 7))

    def add_character_diff(self: Any, report: CharacterDiffReport, verbose: bool = False) -> None:
        visible_sections = tuple(
            section
            for section in report.sections
            if verbose or section.name != "特殊效果"
        )
        self._register_diff_item(
            report.version_one,
            report.version_two,
            f"角色 · {format_name_change(report.name_one, report.name_two)}",
            sum(len(section.changes) for section in visible_sections),
        )
        sections = tuple(section for section in visible_sections if section.status != "unchanged")
        if not sections:
            return
        self._start_item()
        self._ensure_diff_title("角色差异")
        self._resource_heading(format_name_change(report.name_one, report.name_two))
        for section in sections:
            self._subheading(_section_label(section.name))
            if section.name == "基础属性":
                self.story.append(self._change_summary_table([
                    (
                        change.label,
                        self._change_body(change),
                    )
                    for change in section.changes
                ]))
                self.story.append(Spacer(1, 7))
                continue
            self.story.append(self._change_table([
                (
                    character_change_subject(section.name, change),
                    self._change_body(change, style="character"),
                )
                for change in section.changes
            ]))
            self.story.append(Spacer(1, 7))

    def add_lightcone_diff(self: Any, report: LightConeDiffReport) -> None:
        self._register_diff_item(
            report.version_one,
            report.version_two,
            f"光锥 · {format_name_change(report.name_one, report.name_two)}",
            sum(len(section.changes) for section in report.sections),
        )
        sections = report.changed_sections
        if not sections:
            return
        self._start_item()
        self._ensure_diff_title("光锥差异")
        self._resource_heading(format_name_change(report.name_one, report.name_two))
        for section in sections:
            self._subheading(_section_label(section.name))
            if section.name == "基础属性":
                for change in section.changes:
                    self.story.append(_markup_paragraph(
                        f"<b>{_inline_text(change.label)}</b>：{self._change_body(change)}", self.body
                    ))
                    self.story.append(Spacer(1, 4))
                continue
            self.story.append(self._change_table([
                (change.label, self._change_body(change, style="lightcone"))
                for change in section.changes
            ]))
            self.story.append(Spacer(1, 7))

    def add_highmode_diff(self: Any, report: HighModeDiffReport) -> None:
        for section in report.sections:
            self._register_diff_item(
                report.version_one,
                report.version_two,
                _diff_overview_highmode_label(report.mode, section.name),
                len(section.changes) if section.status != "unchanged" else 0,
            )
        sections = report.changed_sections
        if not sections:
            return
        self._start_item()
        self._ensure_diff_title(f"{_pdf_mode_label(report.mode)}差异")
        for section in sections:
            self._heading(_section_label(section.name))
            effect_changes = tuple(change for change in section.changes if change.category == "effects")
            if effect_changes:
                self._subheading("关卡效果")
                self.story.append(self._status_table([
                    self._status_change_row(
                        highmode_change_subject(change),
                        change,
                    )
                    for change in sorted(
                        effect_changes,
                        key=lambda item: (
                            0 if item.kind == "removed" else 1 if item.kind == "added" else 2,
                            item.label,
                        ),
                    )
                ]))
                self.story.append(Spacer(1, 7))

            hp_changes = tuple(change for change in section.changes if change.category == "hp")
            if hp_changes:
                waves: dict[int, list[HighModeChange]] = {}
                for change in hp_changes:
                    wave = highmode_change_wave(change) or 0
                    waves.setdefault(wave, []).append(change)
                for wave, changes in waves.items():
                    self._subheading("首领" if wave == 0 else f"第 {wave} 波", YELLOW)
                    self.story.append(self._status_table([
                        self._status_change_row(
                            highmode_change_subject(change),
                            change,
                        )
                        for change in sorted(
                            changes,
                            key=lambda item: (
                                0 if item.kind == "removed" else 1 if item.kind == "added" else 2,
                                item.label,
                            ),
                        )
                    ]))
                    self.story.append(Spacer(1, 7))

            metadata_changes = tuple(change for change in section.changes if change.category == "metadata")
            if metadata_changes:
                self._subheading("基本信息", CYAN)
                self.story.append(self._change_table([
                    (
                        highmode_change_subject(change),
                        self._change_body(change, style="highmode"),
                    )
                    for change in sorted(
                        metadata_changes,
                        key=lambda item: (
                            0 if item.kind == "removed" else 1 if item.kind == "added" else 2,
                            item.label,
                        ),
                    )
                ]))
                self.story.append(Spacer(1, 7))

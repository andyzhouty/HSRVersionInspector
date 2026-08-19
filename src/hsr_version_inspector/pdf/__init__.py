from __future__ import annotations

from typing import Any, cast

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..character import CharacterSkill, skill_entry_title, skill_group_title
from ..diff import (
    CharacterDiffReport,
    DiffReport,
    HighModeDiffReport,
    LightConeDiffReport,
    format_name_change,
)
from .diff import PdfDiffMixin
from .show import PdfShowMixin
from .support import (
    CYAN,
    DIFF_MODE_SPACING,
    FONT,
    FONT_BOLD,
    INK,
    MAGENTA,
    MARGIN,
    MUTED,
    PAGE_WIDTH,
    RED,
    SYMBOL_FONT,
    _diff_overview_highmode_label,
    _enemy_count_text,
    _markup_paragraph,
    _paragraph,
    _pdf_mode_label,
    _register_fonts,
    _symbol_font_text,
)


class PdfRenderer(PdfShowMixin, PdfDiffMixin):
    """Build rich, colored PDF output directly from the parsed view models."""

    def __init__(self) -> None:
        _register_fonts()
        self.story: list[Any] = []
        self.mode_started = False
        self.mode_title_written = False
        self.mode_item_count = 0
        self.diff_versions: tuple[str, str] | None = None
        self.diff_overview: list[tuple[str, int]] = []
        self.width = PAGE_WIDTH - 2 * MARGIN
        self.title = ParagraphStyle(
            "HviTitle", fontName=FONT_BOLD, fontSize=22, leading=28,
            textColor=INK, spaceAfter=10,
        )
        self.resource_title = ParagraphStyle(
            "HviResourceTitle", fontName=FONT_BOLD, fontSize=18, leading=23,
            textColor=INK, spaceBefore=2, spaceAfter=8,
        )
        self.subtitle = ParagraphStyle(
            "HviSubtitle", fontName=FONT_BOLD, fontSize=14.5, leading=19,
            textColor=CYAN, spaceBefore=11, spaceAfter=6,
        )
        self.subheading = ParagraphStyle(
            "HviSubheading", parent=self.subtitle, fontSize=12, leading=16,
            spaceBefore=7, spaceAfter=4,
        )
        self.body = ParagraphStyle(
            "HviBody", fontName=FONT, fontSize=10, leading=15,
            textColor=INK, spaceAfter=3, splitLongWords=1,
            strikeColor=RED, strikeWidth=0.9, strikeOffset=cast(Any, "0.45*F"),
        )
        self.small = ParagraphStyle(
            "HviSmall", parent=self.body, fontSize=8.5, leading=12,
            textColor=MUTED,
        )
        self.table_body = ParagraphStyle(
            "HviTableBody", parent=self.body, fontSize=9.5, leading=13.5,
            spaceBefore=0, spaceAfter=0,
        )
        self.table_header = ParagraphStyle(
            "HviTableHeader", parent=self.table_body, fontName=FONT_BOLD,
            fontSize=10.5, leading=14, textColor=colors.white,
        )
        self.box_title = ParagraphStyle(
            "HviBoxTitle", parent=self.body, fontName=FONT_BOLD,
            fontSize=11, leading=14.5, textColor=INK,
            spaceBefore=0, spaceAfter=0,
        )

    def _start_item(self) -> None:
        if not self.mode_started:
            if self.story:
                self.story.append(PageBreak())
            self.mode_started = True
        self.mode_item_count += 1

    def begin_mode(self, title: str | None = None) -> None:
        """Start a page group; resources added afterward share this group."""
        if self.story:
            self.story.append(PageBreak())
        self.mode_started = True
        self.mode_title_written = title is not None
        self.mode_item_count = 0
        if title:
            self.story.append(_paragraph(title, self.title))

    def begin_diff_mode(self, title: str | None = None) -> None:
        """Start a diff mode with spacing instead of a page break."""
        if self.story:
            self.story.append(Spacer(1, DIFF_MODE_SPACING))
        self.mode_started = True
        self.mode_title_written = title is not None
        self.mode_item_count = 0
        if title:
            self.story.append(_paragraph(title, self.title))

    def _ensure_diff_title(self, title: str) -> None:
        if self.mode_title_written:
            return
        self.story.append(_paragraph(title, self.title))
        self.mode_title_written = True

    def _heading(self, text: str, color: colors.Color = CYAN) -> None:
        style = ParagraphStyle(
            "HviHeading", parent=self.subtitle, textColor=color,
        )
        self.story.append(_paragraph(text, style))

    def _subheading(self, text: str, color: colors.Color = CYAN) -> None:
        self.story.append(self._subheading_paragraph(text, color))

    def _subheading_paragraph(
        self,
        text: str,
        color: colors.Color = CYAN,
    ) -> Paragraph:
        style = ParagraphStyle(
            "HviSubheading", parent=self.subheading, textColor=color,
        )
        return _paragraph(text, style)

    def _resource_heading(self, text: str, color: colors.Color = INK) -> None:
        style = ParagraphStyle(
            "HviResourceTitle", parent=self.resource_title, textColor=color,
        )
        self.story.append(_paragraph(text, style))

    def _register_diff_item(
        self,
        version_one: str,
        version_two: str,
        label: str,
        change_count: int,
    ) -> None:
        if self.diff_versions is None:
            self.diff_versions = (version_one, version_two)
        if any(existing_label == label for existing_label, _ in self.diff_overview):
            return
        self.diff_overview.append((label, change_count))

    def register_diff_overview(
        self,
        report: DiffReport
        | CharacterDiffReport
        | LightConeDiffReport
        | HighModeDiffReport,
        verbose: bool = False,
    ) -> None:
        if isinstance(report, CharacterDiffReport):
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
            return
        if isinstance(report, LightConeDiffReport):
            self._register_diff_item(
                report.version_one,
                report.version_two,
                f"光锥 · {format_name_change(report.name_one, report.name_two)}",
                sum(len(section.changes) for section in report.sections),
            )
            return
        if isinstance(report, HighModeDiffReport):
            for section in report.sections:
                self._register_diff_item(
                    report.version_one,
                    report.version_two,
                    _diff_overview_highmode_label(report.mode, section.name),
                    len(section.changes) if section.status != "unchanged" else 0,
                )
            return
        for resource in report.resources:
            self._register_diff_item(
                report.version_one,
                report.version_two,
                f"{_pdf_mode_label(report.mode)} · 资源 {resource.resource_id}",
                resource.change_count if resource.status != "unchanged" else 0,
            )

    def _diff_overview_table(self) -> Table | None:
        if not self.diff_overview:
            return None
        data = [
            [
                _paragraph(label, self.table_body),
                _paragraph("无更改" if count == 0 else f"{count} 项", self.table_body),
            ]
            for label, count in self.diff_overview
        ]
        table = Table(
            data,
            colWidths=[self.width * 0.82, self.width * 0.18],
            repeatRows=0,
        )
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#b7c7d8")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _diff_overview_flowables(self) -> list[Any]:
        table = self._diff_overview_table()
        if table is None:
            return []
        version_text = " → ".join(self.diff_versions or ())
        return [
            _paragraph("变更总览", self.title),
            _paragraph(version_text, self.small),
            table,
            Spacer(1, 14),
        ]

    def _table_flowable(
        self,
        headers: tuple[str, ...] | None,
        rows: list[tuple[object, ...]],
        widths: list[float] | None = None,
    ) -> Table:
        if headers is None:
            data = [[_paragraph(item, self.table_body) for item in row] for row in rows]
            column_count = len(rows[0]) if rows else 1
            table = Table(
                data,
                colWidths=widths or [self.width / column_count] * column_count,
                repeatRows=0,
            )
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#b7c7d8")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            return table

        data = [[_paragraph(item, self.table_header) for item in headers]]
        data.extend([[_paragraph(item, self.table_body) for item in row] for row in rows])
        table = Table(data, colWidths=widths or [self.width / len(headers)] * len(headers), repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#b7c7d8")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _summary_table(
        self,
        rows: list[tuple[object, object]],
        widths: list[float] | None = None,
    ) -> Table:
        return self._table_flowable(
            tuple(str(label) for label, _ in rows),
            [tuple(value for _, value in rows)],
            widths,
        )

    def _table(
        self,
        headers: tuple[str, ...],
        rows: list[tuple[object, ...]],
        widths: list[float] | None = None,
    ) -> None:
        table = self._table_flowable(headers, rows, widths)
        self.story.append(table)
        self.story.append(Spacer(1, 6))

    def _change_table(
        self,
        rows: list[tuple[object, str]],
        widths: list[float] | None = None,
    ) -> Table:
        data = [
            [_paragraph(label, self.table_body), _markup_paragraph(body, self.body)]
            for label, body in rows
        ]
        table = Table(
            data,
            colWidths=widths or [self.width * 0.28, self.width * 0.72],
            repeatRows=0,
        )
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#b7c7d8")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _change_summary_table(
        self,
        rows: list[tuple[object, str]],
        widths: list[float] | None = None,
    ) -> Table:
        data = [[_paragraph(label, self.table_header) for label, _ in rows]]
        data.append([_markup_paragraph(value, self.table_body) for _, value in rows])
        table = Table(
            data,
            colWidths=widths or [self.width / len(rows)] * len(rows),
            repeatRows=0,
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#b7c7d8")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _status_table(self, rows: list[tuple[str, str, str]]) -> Table:
        data = [[
            _markup_paragraph(name, self.body),
            _markup_paragraph(status, self.body),
            _markup_paragraph(value, self.body),
        ] for name, status, value in rows]
        table = Table(
            data,
            colWidths=[self.width * 0.24, self.width * 0.12, self.width * 0.64],
            repeatRows=0,
        )
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#b7c7d8")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _box(
        self,
        title: str,
        body: str,
        color: colors.Color = MAGENTA,
        markup: bool = False,
        keep_together: bool = True,
    ) -> None:
        body_paragraph = _markup_paragraph(body, self.body) if markup else _paragraph(body, self.body)
        data = [[_paragraph(title, self.box_title)], [body_paragraph]]
        table = Table(
            data,
            colWidths=[self.width],
            splitByRow=0 if keep_together else 1,
        )
        table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, color),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, color),
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(color.red, color.green, color.blue, alpha=0.12)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 7))

    def _skill_group_box(self, group: tuple[CharacterSkill, ...]) -> None:
        """Render one type as a splittable outer box with separator rows."""
        rows: list[list[Any]] = [[_paragraph(skill_group_title(group), self.box_title)]]
        separator_rows: list[int] = []
        for index, entry in enumerate(group):
            if index:
                separator_rows.append(len(rows))
                rows.append([
                    HRFlowable(
                        width="100%",
                        thickness=0.7,
                        color=MAGENTA,
                        spaceBefore=4,
                        spaceAfter=4,
                    )
                ])
            rows.append([
                [
                    _paragraph(
                        skill_entry_title(group, entry),
                        self.box_title,
                    ),
                    _paragraph(entry.description, self.body),
                ]
            ])
        table = Table(rows, colWidths=[self.width], splitByRow=1)
        style_commands: list[tuple[Any, ...]] = [
            ("BOX", (0, 0), (-1, -1), 0.8, MAGENTA),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, MAGENTA),
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(MAGENTA.red, MAGENTA.green, MAGENTA.blue, alpha=0.12)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]
        for row_index in separator_rows:
            style_commands.extend([
                ("LEFTPADDING", (0, row_index), (-1, row_index), 0),
                ("RIGHTPADDING", (0, row_index), (-1, row_index), 0),
                ("TOPPADDING", (0, row_index), (-1, row_index), 0),
                ("BOTTOMPADDING", (0, row_index), (-1, row_index), 0),
            ])
        table.setStyle(TableStyle(style_commands))
        self.story.append(table)
        self.story.append(Spacer(1, 7))

    def _buffs(self, title: str, buffs: tuple, color: colors.Color = MAGENTA) -> None:
        if not buffs:
            return
        for buff in buffs:
            self._box(buff.name, buff.description, color)

    def _buff_rows(self, buffs: tuple) -> list[list[Any]]:
        return [
            [
                [
                    _paragraph(buff.name, self.box_title),
                    _paragraph(buff.description, self.body),
                ]
            ]
            for buff in buffs
        ]

    def _resource_table(
        self,
        title: str,
        rows: list[list[Any]],
        color: colors.Color = CYAN,
    ) -> None:
        data = [[_paragraph(title, self.resource_title)], *rows]
        table = Table(data, colWidths=[self.width], splitByRow=1)
        table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, color),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, color),
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(color.red, color.green, color.blue, alpha=0.10)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 7))

    def build(self) -> bytes:
        from io import BytesIO

        output = BytesIO()
        document = SimpleDocTemplate(
            output, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN, bottomMargin=MARGIN + 7 * mm,
            title="HSR Version Inspector",
        )

        def footer(canvas: Any, doc: Any) -> None:
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor("#d5dde5"))
            canvas.line(MARGIN, 11 * mm, PAGE_WIDTH - MARGIN, 11 * mm)
            canvas.setFont(FONT, 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(PAGE_WIDTH - MARGIN, 7 * mm, f"第 {doc.page} 页")
            canvas.restoreState()

        document.build(
            [*self._diff_overview_flowables(), *self.story],
            onFirstPage=footer,
            onLaterPages=footer,
        )
        return output.getvalue()


__all__ = ["PdfRenderer", "SYMBOL_FONT", "_enemy_count_text", "_symbol_font_text"]

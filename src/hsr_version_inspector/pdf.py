from __future__ import annotations

from difflib import SequenceMatcher
from html import escape
import json
from pathlib import Path
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .boss import BossView
from .character import (
    CharacterSkill,
    CharacterText,
    CharacterView,
    group_skill_entries,
    skill_entry_title,
    skill_group_title,
)
from .data import VersionRecord
from .diff import (
    CharacterChange,
    CharacterDiffReport,
    DiffReport,
    HighModeChange,
    HighModeDiffReport,
    LightConeChange,
    LightConeDiffReport,
    format_value,
    format_name_change,
    character_change_subject,
    highmode_change_subject,
    highmode_change_wave,
    is_missing,
)
from .highmode import HighModeView
from .lightcone import LightConeView


PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 16 * mm
FONT = "HviCjk"
FONT_BOLD = "HviCjkBold"
SYMBOL_FONT = "HviSymbols"
NUMBER_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?|[^\d]")
RICH_TAG = re.compile(r"\[(/?)(red strike|red|green|white|yellow|cyan|bold)\]")
MODE_LABELS = {
    "character": "角色",
    "lightcone": "光锥",
    "maze": "混沌",
    "story": "虚构",
    "boss": "末日",
    "peak": "异相",
    "knight": "骑士",
    "king": "王棋",
    "hard-king": "绝境",
}
SECTION_LABELS = {
    "Knight 1": "骑士 1",
    "Knight 2": "骑士 2",
    "Knight 3": "骑士 3",
    "King": "王棋",
    "Hard-king": "绝境",
}
ELEMENT_LABELS = {
    "Physical": "物理",
    "Fire": "火",
    "Ice": "冰",
    "Lightning": "雷",
    "Thunder": "雷",
    "Wind": "风",
    "Quantum": "量子",
    "Imaginary": "虚数",
}

CYAN = colors.HexColor("#1877a8")
MAGENTA = colors.HexColor("#8e44ad")
YELLOW = colors.HexColor("#c27c0e")
GREEN = colors.HexColor("#198754")
RED = colors.HexColor("#c0392b")
INK = colors.HexColor("#1e2430")
MUTED = colors.HexColor("#5f6b7a")
LIGHT_BLUE = colors.HexColor("#eaf4fb")
LIGHT_PURPLE = colors.HexColor("#f5edfa")
LIGHT_YELLOW = colors.HexColor("#fff8e5")
NODE_SPACING = 30
DIFF_MODE_SPACING = 45
CHARACTER_SPACING = 30
LIGHTCONE_SPACING = 20


def _register_ttf(name: str, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        kwargs = {"subfontIndex": 0} if path.suffix.lower() in {".ttc", ".otc"} else {}
        pdfmetrics.registerFont(TTFont(name, str(path), **kwargs))
    except Exception:
        return False
    return True


def _register_symbol_font() -> None:
    if SYMBOL_FONT in pdfmetrics.getRegisteredFontNames():
        return
    symbol_paths = (
        Path("/usr/share/fonts/truetype/noto/NotoSansSymbols-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoMusic-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuMathTeXGyre.ttf"),
        Path("/mnt/c/Windows/Fonts/seguisym.ttf"),
        Path("/Windows/Fonts/seguisym.ttf"),
    )
    for path in symbol_paths:
        if _register_ttf(SYMBOL_FONT, path):
            return


def _register_fonts() -> None:
    if FONT in pdfmetrics.getRegisteredFontNames():
        _register_symbol_font()
        return

    # Prefer the requested fonts. TTC files containing CFF outlines are skipped
    # when ReportLab cannot embed them, then the next font in this list is used.
    font_pairs = (
        (
            "Microsoft YaHei",
            (
                Path("/mnt/c/Windows/Fonts/msyh.ttf"),
                Path("/mnt/c/Windows/Fonts/msyh.ttc"),
                Path("/Windows/Fonts/msyh.ttf"),
                Path("/Windows/Fonts/msyh.ttc"),
            ),
            (
                Path("/mnt/c/Windows/Fonts/msyhbd.ttf"),
                Path("/mnt/c/Windows/Fonts/msyhbd.ttc"),
                Path("/Windows/Fonts/msyhbd.ttf"),
                Path("/Windows/Fonts/msyhbd.ttc"),
            ),
        ),
        (
            "Noto Sans CJK",
            (
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttf"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            ),
            (
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttf"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otf"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            ),
        ),
        (
            "兼容中文字体",
            (
                Path("/usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf"),
                Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
            ),
            (),
        ),
    )
    for _, regular_paths, bold_paths in font_pairs:
        regular = next((path for path in regular_paths if _register_ttf(FONT, path)), None)
        if regular is None:
            continue
        bold = next((path for path in bold_paths if _register_ttf(FONT_BOLD, path)), None)
        if bold is None:
            pdfmetrics.registerFont(TTFont(FONT_BOLD, str(regular)))
        _register_symbol_font()
        return

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    globals()["FONT"] = "STSong-Light"
    globals()["FONT_BOLD"] = "STSong-Light"
    _register_symbol_font()


def _symbol_font_text(value: str) -> str:
    if SYMBOL_FONT not in pdfmetrics.getRegisteredFontNames():
        return value
    return value.replace("♪", f'<font name="{SYMBOL_FONT}">♪</font>')


def _multiplication_text(value: str) -> str:
    return value.replace("*", "×")


def _text(value: object) -> str:
    return _symbol_font_text(
        _multiplication_text(escape(str(value))).replace("\n", "<br/>")
    )


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_text(value), style)


def _markup_paragraph(value: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(
        _symbol_font_text(_multiplication_text(value).replace("\n", "<br/>")),
        style,
    )


def _inline_text(value: str) -> str:
    return _multiplication_text(escape(value)).replace("\n", "<br/>")


def _rich_markup_to_pdf(value: str) -> str:
    """Translate the terminal diff markup to equivalent ReportLab markup."""
    colors_by_tag = {
        "red": "#c0392b",
        "green": "#198754",
        "white": "#1e2430",
        "yellow": "#c27c0e",
        "cyan": "#1877a8",
    }
    parts: list[str] = []
    position = 0
    for match in RICH_TAG.finditer(value):
        plain = value[position:match.start()]
        parts.append(_inline_text(plain).replace("\\[", "[").replace("\\]", "]"))
        closing, tag = match.groups()
        if closing:
            if tag == "red strike":
                parts.append("</font></strike>")
            elif tag == "bold":
                parts.append("</b>")
            else:
                parts.append("</font>")
        elif tag == "red strike":
            parts.append('<strike><font color="#c0392b">')
        elif tag == "bold":
            parts.append("<b>")
        else:
            parts.append(f'<font color="{colors_by_tag[tag]}">')
        position = match.end()
    parts.append(_inline_text(value[position:]).replace("\\[", "[").replace("\\]", "]"))
    return "".join(parts)


def _ensure_leading_strike(value: str) -> str:
    # ReportLab can drop the strike line of the first CJK fragment in a
    # wrapped paragraph. A white non-breaking space keeps the same layout
    # while forcing that fragment through the normal strike renderer.
    if value.startswith("<strike>"):
        return '<font color="#ffffff">&#160;</font>' + value
    return value


def _terminal_diff_markup(before: str, after: str, style: str) -> str:
    # Imported lazily because app.py owns the terminal renderer and imports
    # this module during startup.
    from .app import (
        _lightcone_text_markup,
        _rich_text_diff_markup,
        _shared_text_arrow_markup,
        _shared_text_markup,
    )

    if style == "character":
        markup = _shared_text_markup(before, after)
    elif style == "lightcone":
        markup = _lightcone_text_markup(before, after)
    elif style == "hp":
        markup = _rich_text_diff_markup(before, after, arrow=True, whole=True)
    elif style == "status":
        markup = _rich_text_diff_markup(
            before,
            after,
            arrow=False,
            numeric_only=False,
            change_separator=" ",
        )
    else:
        markup = _shared_text_arrow_markup(before, after)
    return _ensure_leading_strike(_rich_markup_to_pdf(markup))


def _enemy_count_text(count: int) -> str:
    return f"×{count}"


def _element_label(element: str) -> str:
    return ELEMENT_LABELS.get(element, element)


def _section_label(value: str) -> str:
    match = re.fullmatch(r"Story (\d+)", value)
    if match:
        return f"虚构节点 {match.group(1)}"
    match = re.fullmatch(r"Maze (\d+)", value)
    if match:
        return f"混沌节点 {match.group(1)}"
    match = re.fullmatch(r"Boss (\d+)", value)
    if match:
        return f"末日节点 {match.group(1)}"
    return SECTION_LABELS.get(value, value)


def _pdf_mode_label(value: str) -> str:
    if value.startswith("story"):
        return "虚构"
    return MODE_LABELS.get(value, value)


def _diff_overview_highmode_label(mode: str, section: str) -> str:
    mode_label = _pdf_mode_label(mode)
    section_label = _section_label(section)
    match = re.fullmatch(r"(Story|Maze|Boss|Knight) (\d+)", section)
    if match:
        if match.group(1) == "Knight" and mode == "peak":
            object_label = f"骑士 · 节点 {match.group(2)}"
        else:
            object_label = f"节点 {match.group(2)}"
    else:
        object_label = section_label
    return mode_label if object_label == mode_label else f"{mode_label} · {object_label}"


def _wave_label(value: str) -> str:
    match = re.fullmatch(r"Wave (\d+)", value)
    return f"第 {match.group(1)} 波" if match else value


def _changed_text(
    before: str,
    after: str,
    numeric_only: bool = False,
    separator: str = "",
) -> str:
    if before == after:
        return _inline_text(before)
    if numeric_only:
        old_numbers = re.findall(r"\d+(?:\.\d+)?%?", before)
        new_numbers = re.findall(r"\d+(?:\.\d+)?%?", after)
        if old_numbers and old_numbers != new_numbers:
            old_text = re.split(r"\d+(?:\.\d+)?%?", before)
            new_text = re.split(r"\d+(?:\.\d+)?%?", after)
            if old_text == new_text:
                parts: list[str] = []
                for index, common in enumerate(old_text):
                    parts.append(_inline_text(common))
                    if index < len(old_numbers):
                        parts.append(
                            f'<strike><font color="#c0392b">{_inline_text(old_numbers[index])}'
                            f'</font></strike>{separator}<font color="#198754">{_inline_text(new_numbers[index])}</font>'
                        )
                return "".join(parts)

    old_tokens = NUMBER_TOKEN.findall(before)
    new_tokens = NUMBER_TOKEN.findall(after)
    matcher = SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    parts = []
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        old_text = "".join(old_tokens[old_start:old_end])
        new_text = "".join(new_tokens[new_start:new_end])
        if tag == "equal":
            parts.append(_inline_text(old_text))
        elif old_text and new_text:
            parts.append(
                f'<strike><font color="#c0392b">{_inline_text(old_text)}</font></strike>'
                f'{separator}<font color="#198754">{_inline_text(new_text)}</font>'
            )
        elif old_text:
            parts.append(
                f'<strike><font color="#c0392b">{_inline_text(old_text)}</font></strike>'
            )
        else:
            parts.append(f'<font color="#198754">{_inline_text(new_text)}</font>')
    return "".join(parts)


class PdfRenderer:
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
            strikeColor=RED, strikeWidth=0.9, strikeOffset="0.45*F",
        )
        self.small = ParagraphStyle(
            "HviSmall", parent=self.body, fontSize=8.5, leading=12,
            textColor=MUTED,
        )
        self.center = ParagraphStyle(
            "HviCenter", parent=self.body, alignment=TA_CENTER,
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
            tuple(label for label, _ in rows),
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

    def add_catalog(self, catalog: tuple[VersionRecord, ...]) -> None:
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

    def add_raw_resource(
        self,
        version: str,
        mode: str,
        resource_id: str,
        payload: object | None,
    ) -> None:
        self._start_item()
        self.story.append(_paragraph(MODE_LABELS.get(mode, mode), self.title))
        self.story.append(self._summary_table(
            [("版本", version), ("资源编号", resource_id)],
            [120, self.width - 120],
        ))
        self.story.append(Spacer(1, 6))
        if payload is None:
            self._box(
                "数据不可用",
                f"未找到本地数据：data/{version}/zh/{mode}/{resource_id}.json。请先运行 hvi download-all。",
                RED,
            )
            return
        self._box(
            "原始 JSON",
            json.dumps(payload, ensure_ascii=False, indent=2),
            YELLOW,
            keep_together=False,
        )

    def add_error(self, title: str, message: str) -> None:
        self._start_item()
        self.story.append(_paragraph(title, self.title))
        self._box("数据读取失败", message, RED)

    def add_boss(self, view: BossView, title: str | None = None) -> None:
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

    def _character_texts(self, title: str, entries: tuple[CharacterText, ...]) -> None:
        if not entries:
            return
        self._heading(title)
        for entry in entries:
            self._box(entry.name, entry.description)

    def _skills(self, title: str, entries: tuple[CharacterSkill, ...]) -> None:
        if not entries:
            return
        self._heading(title)
        for group in group_skill_entries(entries):
            self._skill_group_box(group)

    def add_character(self, view: CharacterView, verbose: bool = False) -> None:
        has_previous_item = self.mode_item_count > 0
        self._start_item()
        if has_previous_item:
            self.story.append(Spacer(1, CHARACTER_SPACING))
        self._resource_heading(view.name)
        summary: list[tuple[object, ...]] = [("角色编号", view.character_id)]
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

    def add_lightcone(self, view: LightConeView) -> None:
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
        self,
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

    def _json_change_body(self, change: Any) -> str:
        if is_missing(change.before):
            return f'<font color="#198754">新增：{_inline_text(format_value(change.after))}</font>'
        if is_missing(change.after):
            return f'<font color="#c0392b">删除：{_inline_text(format_value(change.before))}</font>'
        return _ensure_leading_strike(
            f'<strike><font color="#c0392b">{_inline_text(format_value(change.before))}'
            f'</font></strike> → <font color="#198754">{_inline_text(format_value(change.after))}</font>'
        )

    def _status_change_row(
        self,
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
        self,
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

    def _highmode_change_line(self, change: HighModeChange, label: str, style: str) -> str:
        if change.kind == "changed":
            return f"<b>{_inline_text(label)}</b>：{self._change_body(change, style=style)}"
        action = "新增" if change.kind == "added" else "删除"
        value = change.after if change.kind == "added" else change.before
        color = "#198754" if change.kind == "added" else "#c0392b"
        return (
            f'<font color="{color}">{action}：<b>{_inline_text(label)}</b>：'
            f"{_inline_text(value or '')}</font>"
        )

    def add_no_changes(self) -> None:
        self.story.append(_paragraph("未发现变更。", self.body))

    def add_diff(self, report: DiffReport) -> None:
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

    def _add_section_table(self, sections: list[tuple[str, int]]) -> None:
        self._table(
            ("分类", "变更数"),
            [(_section_label(name), count) for name, count in sections],
            [self.width * 0.7, self.width * 0.3],
        )

    def add_character_diff(self, report: CharacterDiffReport, verbose: bool = False) -> None:
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

    def add_lightcone_diff(self, report: LightConeDiffReport) -> None:
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

    def add_highmode_diff(self, report: HighModeDiffReport) -> None:
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

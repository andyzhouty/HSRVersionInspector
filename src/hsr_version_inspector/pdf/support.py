"""Font, style, and text primitives shared by PDF components."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

from ..output.diff_markup import (
    lightcone_text_markup as _lightcone_text_markup,
)
from ..output.diff_markup import (
    rich_text_diff_markup as _rich_text_diff_markup,
)
from ..output.diff_markup import (
    shared_text_arrow_markup as _shared_text_arrow_markup,
)
from ..output.diff_markup import (
    shared_text_markup as _shared_text_markup,
)
from ..output.labels import ELEMENT_LABELS, MODE_LABELS

PAGE_WIDTH = A4[0]
MARGIN = 16 * mm
FONT = "HviCjk"
FONT_BOLD = "HviCjkBold"
SYMBOL_FONT = "HviSymbols"
NUMBER_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?|[^\d]")
RICH_TAG = re.compile(r"\[(/?)(red strike|red|green|white|yellow|cyan|bold)\]")
SECTION_LABELS = {
    "Knight 1": "骑士 1",
    "Knight 2": "骑士 2",
    "Knight 3": "骑士 3",
    "King": "王棋",
    "Hard-king": "绝境",
}
CYAN = colors.HexColor("#1877a8")
MAGENTA = colors.HexColor("#8e44ad")
YELLOW = colors.HexColor("#c27c0e")
RED = colors.HexColor("#c0392b")
INK = colors.HexColor("#1e2430")
MUTED = colors.HexColor("#5f6b7a")
NODE_SPACING = 30
DIFF_MODE_SPACING = 45
CHARACTER_SPACING = 30
LIGHTCONE_SPACING = 20


def _register_ttf(name: str, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        if path.suffix.lower() in {".ttc", ".otc"}:
            font = TTFont(name, str(path), subfontIndex=0)
        else:
            font = TTFont(name, str(path))
        pdfmetrics.registerFont(font)
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

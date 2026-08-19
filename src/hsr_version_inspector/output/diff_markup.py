"""Rich markup for semantic text differences.

The tokenizer lives in the domain diff module; this adapter only decides how
the already-tokenized parts are represented for terminal-like output.
"""

from __future__ import annotations

from rich.markup import escape

from ..diff import tokenize_refinement_diff, tokenize_text_diff
from .text import terminal_text


def rich_text_diff_markup(
    old_value: str,
    new_value: str,
    *,
    arrow: bool,
    numeric_only: bool = True,
    whole: bool = False,
    refinement: bool = False,
    change_separator: str = "",
    convert_multiplication: bool = False,
) -> str:
    """Render a tokenized difference using Rich markup.

    This function intentionally contains no output-channel branching. Markdown
    adapters can translate the resulting semantic Rich subset consistently.
    """
    if convert_multiplication:
        old_value = terminal_text(old_value)
        new_value = terminal_text(new_value)
    parts = (
        tokenize_refinement_diff(old_value, new_value)
        if refinement
        else tokenize_text_diff(
            old_value,
            new_value,
            numeric_only=numeric_only,
            whole=whole,
        )
    )
    if parts is None:
        parts = tokenize_text_diff(
            old_value,
            new_value,
            numeric_only=numeric_only,
            whole=whole,
        )
    rendered: list[str] = []
    for index, part in enumerate(parts):
        text = escape(part.text)
        if part.kind == "equal":
            rendered.append(text)
        elif part.kind == "removed":
            tag = "red" if arrow else "red strike"
            rendered.append(f"[{tag}]{text}[/{tag}]")
        else:
            separator = ""
            if index > 0 and parts[index - 1].kind == "removed":
                separator = " -> " if arrow else change_separator
            rendered.append(f"{separator}[green]{text}[/green]")
    return "".join(rendered)


def shared_text_markup(old_value: str, new_value: str) -> str:
    return rich_text_diff_markup(
        old_value,
        new_value,
        arrow=False,
        convert_multiplication=True,
    )


def shared_text_arrow_markup(old_value: str, new_value: str) -> str:
    return rich_text_diff_markup(
        old_value,
        new_value,
        arrow=True,
        convert_multiplication=True,
    )


def lightcone_text_markup(old_value: str, new_value: str) -> str:
    return rich_text_diff_markup(
        old_value,
        new_value,
        arrow=False,
        refinement=True,
        convert_multiplication=True,
    )


def markdown_shared_text_markup(old_value: str, new_value: str) -> str:
    return rich_text_diff_markup(old_value, new_value, arrow=False)


def markdown_shared_text_arrow_markup(old_value: str, new_value: str) -> str:
    return rich_text_diff_markup(old_value, new_value, arrow=True)


def markdown_lightcone_text_markup(old_value: str, new_value: str) -> str:
    return rich_text_diff_markup(
        old_value,
        new_value,
        arrow=False,
        refinement=True,
    )

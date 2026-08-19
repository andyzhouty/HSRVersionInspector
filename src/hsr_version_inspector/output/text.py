"""Format-independent text transformations used by renderers."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any


def terminal_text(value: object) -> str:
    """Use the mathematical multiplication sign in terminal output."""
    return str(value).replace("*", "×")


def markdown_text(value: object) -> str:
    """Escape text that is inserted into Markdown prose or table cells."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("*", "\\*")
        .replace("_", "\\_")
    )


def markdown_cell(value: object) -> str:
    return markdown_text(value).replace("|", "\\|").replace("\n", "<br>")


def markdown_markup_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def rich_markup_to_markdown(value: str) -> str:
    """Convert the small Rich markup subset used by semantic renderers."""
    replacements = (
        ("[red strike]", "~~"),
        ("[/red strike]", "~~"),
        ("[red]", "~~"),
        ("[/red]", "~~"),
        ("[green]", ""),
        ("[/green]", ""),
        ("[bold]", "**"),
        ("[/bold]", "**"),
    )
    for source, target in replacements:
        value = value.replace(source, target)
    return re.sub(r"\[[^\]]+\]", "", value)


def markdown_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
    *,
    markup_rows: bool = False,
) -> list[str]:
    cell = markdown_markup_cell if markup_rows else markdown_cell
    lines = [
        "| " + " | ".join(markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(cell(value) for value in row) + " |"
        for row in rows
    )
    return lines


def enemy_count_text(count: int) -> str:
    return f"×{count}"


def markdown_enemy_count_text(count: int) -> str:
    return f"*{count}"


def unique_by_name_and_description(items: Iterable[Any], seen: set[tuple[str, str]]) -> tuple[Any, ...]:
    """Remove repeated effect entries while preserving source order."""
    unique: list[Any] = []
    for item in items:
        key = (item.name, item.description)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return tuple(unique)

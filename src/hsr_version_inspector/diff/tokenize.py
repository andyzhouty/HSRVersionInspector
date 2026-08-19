"""Shared tokenization for terminal, Markdown, and PDF differences."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

TEXT_DIFF_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
TEXT_DIFF_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?|[^\d]")
REFINEMENT_GROUP = re.compile(r"\d+(?:\.\d+)?%?(?:/\d+(?:\.\d+)?%?)+")


@dataclass(frozen=True)
class TextDiffPart:
    kind: str
    text: str


def tokenize_text_diff(
    before: str,
    after: str,
    *,
    numeric_only: bool = True,
    whole: bool = False,
) -> tuple[TextDiffPart, ...]:
    """Return one stable tokenization for all human-readable diff renderers."""
    if before == after:
        return (TextDiffPart("equal", before),) if before else ()
    if whole:
        return (TextDiffPart("removed", before), TextDiffPart("added", after))

    if numeric_only:
        before_numbers = TEXT_DIFF_NUMBER.findall(before)
        after_numbers = TEXT_DIFF_NUMBER.findall(after)
        before_text = TEXT_DIFF_NUMBER.split(before)
        after_text = TEXT_DIFF_NUMBER.split(after)
        if before_numbers and before_text == after_text:
            numeric_parts: list[TextDiffPart] = []
            for index, common in enumerate(before_text):
                if common:
                    numeric_parts.append(TextDiffPart("equal", common))
                if index >= len(before_numbers):
                    continue
                old_number = before_numbers[index]
                new_number = after_numbers[index]
                if old_number == new_number:
                    numeric_parts.append(TextDiffPart("equal", old_number))
                else:
                    numeric_parts.extend((TextDiffPart("removed", old_number), TextDiffPart("added", new_number)))
            return tuple(numeric_parts)

    old_tokens = TEXT_DIFF_TOKEN.findall(before)
    new_tokens = TEXT_DIFF_TOKEN.findall(after)
    matcher = SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    parts: list[TextDiffPart] = []
    opcodes = matcher.get_opcodes()
    pending_old: list[str] = []
    pending_new: list[str] = []

    def flush_pending() -> None:
        if not pending_old and not pending_new:
            return
        old_text = "".join(pending_old)
        new_text = "".join(pending_new)
        if old_text:
            parts.append(TextDiffPart("removed", old_text))
        if new_text:
            parts.append(TextDiffPart("added", new_text))
        pending_old.clear()
        pending_new.clear()

    for index, (tag, old_start, old_end, new_start, new_end) in enumerate(opcodes):
        old_text = "".join(old_tokens[old_start:old_end])
        new_text = "".join(new_tokens[new_start:new_end])
        if tag == "equal":
            previous_changed = index > 0 and opcodes[index - 1][0] != "equal"
            next_changed = index + 1 < len(opcodes) and opcodes[index + 1][0] != "equal"
            wrapped_by_insertions = (
                previous_changed
                and next_changed
                and opcodes[index - 1][0] == "insert"
                and opcodes[index + 1][0] == "insert"
            )
            if wrapped_by_insertions:
                flush_pending()
                if old_text:
                    parts.append(TextDiffPart("equal", old_text))
            elif len(old_text) < 5 and previous_changed and next_changed:
                pending_old.append(old_text)
                pending_new.append(new_text)
            else:
                flush_pending()
                if old_text:
                    parts.append(TextDiffPart("equal", old_text))
            continue
        pending_old.append(old_text)
        pending_new.append(new_text)
    flush_pending()
    return tuple(parts)

def tokenize_refinement_diff(before: str, after: str) -> tuple[TextDiffPart, ...] | None:
    """Keep each slash-separated light-cone refinement group as one token."""
    old_matches = tuple(REFINEMENT_GROUP.finditer(before))
    new_matches = tuple(REFINEMENT_GROUP.finditer(after))
    if not old_matches or len(old_matches) != len(new_matches):
        return None
    if REFINEMENT_GROUP.sub("", before) != REFINEMENT_GROUP.sub("", after):
        return None

    parts: list[TextDiffPart] = []
    old_cursor = 0
    new_cursor = 0
    for old_match, new_match in zip(old_matches, new_matches):
        old_common = before[old_cursor:old_match.start()]
        new_common = after[new_cursor:new_match.start()]
        if old_common != new_common:
            return None
        if old_common:
            parts.append(TextDiffPart("equal", old_common))
        old_group = old_match.group(0)
        new_group = new_match.group(0)
        if old_group == new_group:
            parts.append(TextDiffPart("equal", old_group))
        else:
            parts.extend((TextDiffPart("removed", old_group), TextDiffPart("added", new_group)))
        old_cursor = old_match.end()
        new_cursor = new_match.end()

    tail_old = before[old_cursor:]
    tail_new = after[new_cursor:]
    if tail_old != tail_new:
        return None
    if tail_old:
        parts.append(TextDiffPart("equal", tail_old))
    return tuple(parts)

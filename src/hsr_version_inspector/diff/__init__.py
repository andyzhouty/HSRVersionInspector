"""Compatibility facade for version comparison.

The comparison domains live in diff_common, diff_character, diff_lightcone
and diff_highmode. This module intentionally keeps the historical import
surface stable for callers and plugins.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..boss import available_boss_nodes, load_boss
from ..data import VersionRecord
from ..paths import DATA_DIR
from .character import (
    compare_all_character_versions,
    compare_character_versions,
)
from .common import (
    DIFF_MODES,
    MISSING,
    compare_versions,
    format_name_change,
    format_value,
    highmode_change_subject,
    highmode_change_wave,
    is_missing,
    supported_modes_text,
    validate_request,
)
from .highmode import (
    compare_all_boss_versions as _compare_all_boss_versions,
)
from .highmode import (
    compare_all_maze_versions,
    compare_all_story_versions,
    compare_highmode_versions,
    compare_maze_versions,
)
from .highmode import (
    compare_boss_versions as _compare_boss_versions,
)
from .lightcone import (
    compare_all_lightcone_versions,
    compare_lightcone_versions,
)
from .models import (
    CharacterChange,
    CharacterDiffReport,
    CharacterSectionDiff,
    DiffReport,
    HighModeChange,
    HighModeDiffReport,
    HighModeSectionDiff,
    JsonChange,
    LightConeChange,
    LightConeDiffReport,
    LightConeSectionDiff,
    ResourceDiff,
)
from .tokenize import (
    TextDiffPart,
    tokenize_refinement_diff,
    tokenize_text_diff,
)

BASE_STAT_ORDER = {
    "命途": -1,
    "生命值": 0,
    "攻击力": 1,
    "防御力": 2,
    "速度": 3,
}
CHARACTER_SKILL_LABEL = re.compile(r"^(?P<type>.+?) \d+级 · (?P<name>.+)$")


def character_change_subject(section: str, change: CharacterChange) -> str:
    """Use skill type names unless a skill was added or removed by name."""
    if section != "技能" and not section.startswith("忆灵 · "):
        return change.label
    match = CHARACTER_SKILL_LABEL.fullmatch(change.label)
    if match is None:
        return change.label
    if change.kind == "changed":
        return match.group("type")
    return f"{match.group('type')} · {match.group('name')}"


def compare_boss_versions(
    version_one: str,
    version_two: str,
    node: int,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> HighModeDiffReport:
    return _compare_boss_versions(
        version_one,
        version_two,
        node,
        record_one,
        record_two,
        data_root,
        load_boss_fn=load_boss,
    )


def compare_all_boss_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[HighModeDiffReport, ...]:
    return _compare_all_boss_versions(
        version_one,
        version_two,
        record_one,
        record_two,
        data_root,
        available_boss_nodes_fn=available_boss_nodes,
        load_boss_fn=load_boss,
    )


__all__ = [
    "BASE_STAT_ORDER",
    "CharacterChange",
    "CharacterDiffReport",
    "CharacterSectionDiff",
    "DIFF_MODES",
    "DiffReport",
    "HighModeChange",
    "HighModeDiffReport",
    "HighModeSectionDiff",
    "JsonChange",
    "LightConeChange",
    "LightConeDiffReport",
    "LightConeSectionDiff",
    "MISSING",
    "ResourceDiff",
    "TextDiffPart",
    "character_change_subject",
    "compare_all_boss_versions",
    "compare_all_character_versions",
    "compare_all_lightcone_versions",
    "compare_all_maze_versions",
    "compare_all_story_versions",
    "compare_boss_versions",
    "compare_character_versions",
    "compare_highmode_versions",
    "compare_lightcone_versions",
    "compare_maze_versions",
    "compare_versions",
    "format_name_change",
    "format_value",
    "highmode_change_subject",
    "highmode_change_wave",
    "is_missing",
    "supported_modes_text",
    "tokenize_refinement_diff",
    "tokenize_text_diff",
    "validate_request",
]

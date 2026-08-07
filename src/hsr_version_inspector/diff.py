from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .boss import available_boss_nodes, load_boss
from .character import CharacterView, load_character
from .data import VersionRecord
from .highmode import (
    HighModeView,
    available_maze_nodes,
    load_maze,
    load_peak,
    load_story,
)
from .lightcone import LightConeView, load_lightcone


DATA_DIR = Path("data")
DIFF_MODES = (
    "character",
    "lightcone",
    "maze",
    "story",
    "boss",
    "peak",
    "knight",
    "king",
    "hard-king",
)
DIFF_MODE_LABELS = {
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
_INTERNAL_DIFF_MODES = {*DIFF_MODES, "story"}
MAX_STORED_CHANGES = 80
MISSING = object()
BASE_STAT_ORDER = {
    "生命值": 0,
    "攻击力": 1,
    "防御力": 2,
    "速度": 3,
}
TEXT_DIFF_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
TEXT_DIFF_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?|[^\d]")
REFINEMENT_GROUP = re.compile(
    r"\d+(?:\.\d+)?%?(?:/\d+(?:\.\d+)?%?)+"
)
CHARACTER_SKILL_LABEL = re.compile(r"^(?P<type>.+?) \d+级 · (?P<name>.+)$")


@dataclass(frozen=True)
class JsonChange:
    path: str
    before: Any
    after: Any


@dataclass(frozen=True)
class ResourceDiff:
    resource_id: str
    status: str
    change_count: int
    changes: tuple[JsonChange, ...]


@dataclass(frozen=True)
class DiffReport:
    version_one: str
    version_two: str
    mode: str
    resources: tuple[ResourceDiff, ...]

    @property
    def changed_resources(self) -> tuple[ResourceDiff, ...]:
        return tuple(
            resource
            for resource in self.resources
            if resource.status in {"changed", "added", "removed"}
        )


@dataclass(frozen=True)
class CharacterChange:
    label: str
    before: str | None
    after: str | None
    kind: str


@dataclass(frozen=True)
class CharacterSectionDiff:
    name: str
    status: str
    changes: tuple[CharacterChange, ...]


@dataclass(frozen=True)
class CharacterDiffReport:
    version_one: str
    version_two: str
    character_index: int
    character_id_one: str
    character_id_two: str
    name_one: str
    name_two: str
    sections: tuple[CharacterSectionDiff, ...]

    @property
    def changed_sections(self) -> tuple[CharacterSectionDiff, ...]:
        return tuple(section for section in self.sections if section.status != "unchanged")


@dataclass(frozen=True)
class LightConeChange:
    label: str
    before: str | None
    after: str | None
    kind: str


@dataclass(frozen=True)
class LightConeSectionDiff:
    name: str
    status: str
    changes: tuple[LightConeChange, ...]


@dataclass(frozen=True)
class LightConeDiffReport:
    version_one: str
    version_two: str
    lightcone_index: int
    lightcone_id_one: str
    lightcone_id_two: str
    name_one: str
    name_two: str
    sections: tuple[LightConeSectionDiff, ...]

    @property
    def changed_sections(self) -> tuple[LightConeSectionDiff, ...]:
        return tuple(section for section in self.sections if section.status != "unchanged")


@dataclass(frozen=True)
class HighModeChange:
    category: str
    label: str
    before: str | None
    after: str | None
    kind: str
    wave: int | None = None
    subject: str | None = None


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
            parts: list[TextDiffPart] = []
            for index, common in enumerate(before_text):
                if common:
                    parts.append(TextDiffPart("equal", common))
                if index >= len(before_numbers):
                    continue
                old_number = before_numbers[index]
                new_number = after_numbers[index]
                if old_number == new_number:
                    parts.append(TextDiffPart("equal", old_number))
                else:
                    parts.extend((
                        TextDiffPart("removed", old_number),
                        TextDiffPart("added", new_number),
                    ))
            return tuple(parts)

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


def tokenize_refinement_diff(
    before: str,
    after: str,
) -> tuple[TextDiffPart, ...] | None:
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
            parts.extend((
                TextDiffPart("removed", old_group),
                TextDiffPart("added", new_group),
            ))
        old_cursor = old_match.end()
        new_cursor = new_match.end()

    tail_old = before[old_cursor:]
    tail_new = after[new_cursor:]
    if tail_old != tail_new:
        return None
    if tail_old:
        parts.append(TextDiffPart("equal", tail_old))
    return tuple(parts)


@dataclass(frozen=True)
class HighModeSectionDiff:
    name: str
    status: str
    changes: tuple[HighModeChange, ...]


@dataclass(frozen=True)
class HighModeDiffReport:
    version_one: str
    version_two: str
    mode: str
    sections: tuple[HighModeSectionDiff, ...]

    @property
    def changed_sections(self) -> tuple[HighModeSectionDiff, ...]:
        return tuple(section for section in self.sections if section.status != "unchanged")


def highmode_change_subject(change: HighModeChange) -> str:
    if change.subject is not None:
        return change.subject
    if ": " in change.label:
        return change.label.split(": ", 1)[1]
    return change.label


def highmode_change_wave(change: HighModeChange) -> int | None:
    if change.wave is not None:
        return change.wave
    match = re.match(r"Wave (\d+): ", change.label)
    return int(match.group(1)) if match else None


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


def version_family(version: str) -> str:
    parts = version.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else version


def _mode_label(mode: str) -> str:
    if mode.startswith("story "):
        return f"虚构节点 {mode.removeprefix('story ')}"
    return DIFF_MODE_LABELS.get(mode, mode)


def supported_modes_text() -> str:
    return "、".join(f"{_mode_label(mode)}（{mode}）" for mode in DIFF_MODES)


def validate_request(
    record_one: VersionRecord,
    record_two: VersionRecord,
    version_one: str,
    version_two: str,
    mode: str,
) -> None:
    if mode not in _INTERNAL_DIFF_MODES:
        raise ValueError(f"不支持的比较模式 {mode!r}。")
    if version_one == version_two:
        raise ValueError("两个版本必须是不同的版本。")
    if version_family(version_one) != version_family(version_two):
        raise ValueError("只能比较主版本号和次版本号相同的版本线。")
    if record_one.name != record_two.name:
        raise ValueError("只能比较同一版本目录项中的版本。")
    resource_mode = "peak" if mode in {"knight", "king", "hard-king"} else mode
    if not _resource_ids(record_one, resource_mode) or not _resource_ids(record_two, resource_mode):
        raise ValueError(f"此版本线未配置 {_mode_label(mode)} 资源。")


def _resource_ids(record: VersionRecord, mode: str) -> tuple[str, ...]:
    value = getattr(record, mode)
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(value)


def _resource_path(data_root: Path, version: str, mode: str, resource_id: str) -> Path:
    return data_root / version / "zh" / mode / f"{resource_id}.json"


def _read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return MISSING


def _path_key(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}[{json.dumps(key, ensure_ascii=False)}]"


def _compare_values(
    before: Any,
    after: Any,
    path: str,
    changes: list[JsonChange],
) -> int:
    if before is MISSING and after is MISSING:
        return 0
    if before is MISSING or after is MISSING:
        if len(changes) < MAX_STORED_CHANGES:
            changes.append(JsonChange(path, before, after))
        return 1
    if type(before) is not type(after):
        if len(changes) < MAX_STORED_CHANGES:
            changes.append(JsonChange(path, before, after))
        return 1
    if isinstance(before, dict):
        total = 0
        keys = sorted(set(before) | set(after), key=str)
        for key in keys:
            total += _compare_values(
                before.get(key, MISSING),
                after.get(key, MISSING),
                _path_key(path, str(key)),
                changes,
            )
        return total
    if isinstance(before, list):
        total = 0
        for index in range(max(len(before), len(after))):
            old_value = before[index] if index < len(before) else MISSING
            new_value = after[index] if index < len(after) else MISSING
            total += _compare_values(old_value, new_value, _path_key(path, index), changes)
        return total
    if before == after:
        return 0
    if len(changes) < MAX_STORED_CHANGES:
        changes.append(JsonChange(path, before, after))
    return 1


def compare_versions(
    version_one: str,
    version_two: str,
    mode: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> DiffReport:
    validate_request(record_one, record_two, version_one, version_two, mode)
    resource_ids = tuple(dict.fromkeys((*_resource_ids(record_one, mode), *_resource_ids(record_two, mode))))
    resources: list[ResourceDiff] = []
    for resource_id in resource_ids:
        before = _read_json(_resource_path(data_root, version_one, mode, resource_id))
        after = _read_json(_resource_path(data_root, version_two, mode, resource_id))
        changes: list[JsonChange] = []
        change_count = _compare_values(before, after, "$", changes)
        if before is MISSING and after is MISSING:
            status = "missing"
        elif before is MISSING:
            status = "added"
        elif after is MISSING:
            status = "removed"
        elif change_count:
            status = "changed"
        else:
            status = "unchanged"
        resources.append(
            ResourceDiff(resource_id, status, change_count, tuple(changes))
        )
    return DiffReport(version_one, version_two, mode, tuple(resources))


def format_value(value: Any) -> str:
    if value is MISSING:
        return "<缺失>"
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(text) > 180:
        return f"{text[:177]}..."
    return text


def format_name_change(name_one: str, name_two: str) -> str:
    return name_one if name_one == name_two else f"{name_one} → {name_two}"


def is_missing(value: Any) -> bool:
    return value is MISSING


def _character_skill_map(view: CharacterView, memosprite: bool = False) -> dict[str, str]:
    skills = view.memosprite_skills if memosprite else view.skills
    return {
        f"{skill.type_name} {skill.level}级 · {skill.name}": skill.description
        for skill in skills
    }


def _character_text_map(entries: tuple[Any, ...]) -> dict[str, str]:
    return {entry.name: entry.description for entry in entries}


def _character_base_stat_map(view: CharacterView) -> dict[str, str]:
    if view.base_stats is None:
        return {}
    return {
        "基础生命值": view.base_stats.hp,
        "基础攻击力": view.base_stats.attack,
        "基础防御力": view.base_stats.defence,
        "基础速度": view.base_stats.speed,
    }


def _character_eidolon_map(view: CharacterView) -> dict[str, str]:
    return {
        f"星魂 {index} · {entry.name}": entry.description
        for index, entry in enumerate(view.eidolons, 1)
    }


def _lightcone_text_map(view: LightConeView) -> dict[str, str]:
    return {
        "等级": f"{view.level}级",
        "稀有度": f"{view.rarity}星",
        "命途": view.path,
        "生命值": view.hp,
        "攻击力": view.attack,
        "防御力": view.defence,
    }


def _lightcone_effect_map(view: LightConeView) -> dict[str, str]:
    return {view.refinement_name: view.description}


def _character_section(
    name: str,
    before: dict[str, str],
    after: dict[str, str],
) -> CharacterSectionDiff:
    changes: list[CharacterChange] = []
    for label in sorted(set(before) | set(after), key=_section_change_sort_key):
        old = before.get(label)
        new = after.get(label)
        if old == new:
            continue
        kind = "added" if old is None else "removed" if new is None else "changed"
        changes.append(CharacterChange(label, old, new, kind))
    return CharacterSectionDiff(name, "changed" if changes else "unchanged", tuple(changes))


def _lightcone_section(
    name: str,
    before: dict[str, str],
    after: dict[str, str],
) -> LightConeSectionDiff:
    changes: list[LightConeChange] = []
    for label in sorted(set(before) | set(after), key=_section_change_sort_key):
        old = before.get(label)
        new = after.get(label)
        if old == new:
            continue
        kind = "added" if old is None else "removed" if new is None else "changed"
        changes.append(LightConeChange(label, old, new, kind))
    return LightConeSectionDiff(name, "changed" if changes else "unchanged", tuple(changes))


def _section_change_sort_key(label: str) -> tuple[int, int | str]:
    stat_name = label.removeprefix("基础")
    if stat_name in BASE_STAT_ORDER:
        return (0, BASE_STAT_ORDER[stat_name])
    return (1, label)


def compare_character_versions(
    version_one: str,
    version_two: str,
    node: int | None,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> CharacterDiffReport:
    if node is None or node < 1:
        raise ValueError("角色比较需要提供序号，例如 character 1。")
    validate_request(record_one, record_two, version_one, version_two, "character")
    ids_one = _resource_ids(record_one, "character")
    ids_two = _resource_ids(record_two, "character")
    if node > len(ids_one) or node > len(ids_two):
        raise ValueError(f"角色序号 {node} 在两个版本中未同时存在。")
    character_id_one = ids_one[node - 1]
    character_id_two = ids_two[node - 1]
    before = load_character(version_one, character_id_one, data_root)
    after = load_character(version_two, character_id_two, data_root)
    sections: list[CharacterSectionDiff] = []
    if before.base_stats or after.base_stats:
        sections.append(
            _character_section(
                "基础属性",
                _character_base_stat_map(before),
                _character_base_stat_map(after),
            )
        )
    sections.append(
        _character_section(
            "技能",
            _character_skill_map(before),
            _character_skill_map(after),
        )
    )
    if (
        before.memosprite_name
        or after.memosprite_name
        or before.memosprite_skills
        or after.memosprite_skills
    ):
        sections.append(
            _character_section(
                f"忆灵 · {before.memosprite_name or after.memosprite_name or '-'}",
                _character_skill_map(before, True),
                _character_skill_map(after, True),
            )
        )
    sections.extend(
        [
            _character_section(
                "行迹",
                {
                    **_character_text_map(before.traces),
                    **{
                        f"属性 · {entry.name}": entry.description
                        for entry in before.trace_stats
                    },
                },
                {
                    **_character_text_map(after.traces),
                    **{
                        f"属性 · {entry.name}": entry.description
                        for entry in after.trace_stats
                    },
                },
            ),
            _character_section(
                "特殊效果",
                _character_text_map(before.special_effects),
                _character_text_map(after.special_effects),
            ),
            _character_section(
                "星魂",
                _character_eidolon_map(before),
                _character_eidolon_map(after),
            ),
        ]
    )
    return CharacterDiffReport(
        version_one,
        version_two,
        node,
        character_id_one,
        character_id_two,
        before.name,
        after.name,
        tuple(sections),
    )


def compare_all_character_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[CharacterDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "character")
    ids_one = _resource_ids(record_one, "character")
    ids_two = _resource_ids(record_two, "character")
    if len(ids_one) != len(ids_two):
        raise ValueError(
            "不指定角色序号时，两个版本必须拥有相同长度的角色列表。"
        )
    return tuple(
        compare_character_versions(
            version_one,
            version_two,
            index,
            record_one,
            record_two,
            data_root,
        )
        for index in range(1, len(ids_one) + 1)
    )


def compare_lightcone_versions(
    version_one: str,
    version_two: str,
    node: int,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> LightConeDiffReport:
    if node < 1:
        raise ValueError("光锥比较需要提供正整数序号，例如 lightcone 1。")
    validate_request(record_one, record_two, version_one, version_two, "lightcone")
    ids_one = _resource_ids(record_one, "lightcone")
    ids_two = _resource_ids(record_two, "lightcone")
    if node > len(ids_one) or node > len(ids_two):
        raise ValueError(f"光锥序号 {node} 在两个版本中未同时存在。")
    lightcone_id_one = ids_one[node - 1]
    lightcone_id_two = ids_two[node - 1]
    before = load_lightcone(version_one, lightcone_id_one, data_root)
    after = load_lightcone(version_two, lightcone_id_two, data_root)
    sections = (
        _lightcone_section("基础属性", _lightcone_text_map(before), _lightcone_text_map(after)),
        _lightcone_section("光锥效果", _lightcone_effect_map(before), _lightcone_effect_map(after)),
    )
    return LightConeDiffReport(
        version_one,
        version_two,
        node,
        lightcone_id_one,
        lightcone_id_two,
        before.name,
        after.name,
        sections,
    )


def compare_all_lightcone_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[LightConeDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "lightcone")
    ids_one = _resource_ids(record_one, "lightcone")
    ids_two = _resource_ids(record_two, "lightcone")
    if len(ids_one) != len(ids_two):
        raise ValueError(
            "不指定光锥序号时，两个版本必须拥有相同长度的光锥列表。"
        )
    return tuple(
        compare_lightcone_versions(
            version_one,
            version_two,
            index,
            record_one,
            record_two,
            data_root,
        )
        for index in range(1, len(ids_one) + 1)
    )


def _effect_map(view: HighModeView) -> dict[tuple[str, str], str]:
    effects: dict[tuple[str, str], str] = {}
    for scope, buffs in (("Season", view.season_buffs), ("Stage", view.buffs)):
        for buff in buffs:
            effects[(scope, buff.name)] = buff.description
    return effects


def _hp_map(view: HighModeView) -> dict[tuple[int, str], str]:
    values: dict[tuple[int, str], str] = {}
    for wave in view.waves:
        for enemy in wave.enemies:
            phase_hps = enemy.phase_hps or (enemy.hp,)
            if len(phase_hps) == 1:
                hp = f"HP {phase_hps[0]:,}"
            elif len(set(phase_hps)) == 1:
                hp = f"HP {phase_hps[0]:,} × {len(phase_hps)}"
            else:
                hp = " / ".join(
                    f"第{phase}阶段：{value:,}" for phase, value in enumerate(phase_hps, 1)
                )
            count = f"×{enemy.count}；" if enemy.count > 1 else ""
            values[(wave.number, enemy.name)] = f"{count}{hp}"
    return values


def _view_changes(before: HighModeView, after: HighModeView) -> tuple[HighModeChange, ...]:
    changes: list[HighModeChange] = []

    def add(
        category: str,
        label: str,
        old: str | None,
        new: str | None,
        *,
        wave: int | None = None,
        subject: str | None = None,
    ) -> None:
        if old != new:
            kind = "added" if old is None else "removed" if new is None else "changed"
            changes.append(HighModeChange(category, label, old, new, kind, wave, subject))

    add("metadata", "Title", before.title, after.title)
    add("metadata", "Level", str(before.level), str(after.level))

    before_effects = _effect_map(before)
    after_effects = _effect_map(after)
    for key in sorted(set(before_effects) | set(after_effects)):
        scope, name = key
        add(
            "effects",
            f"{scope}: {name}",
            before_effects.get(key),
            after_effects.get(key),
            subject=name,
        )

    before_hp = _hp_map(before)
    after_hp = _hp_map(after)
    for key in sorted(set(before_hp) | set(after_hp)):
        wave, name = key
        add(
            "hp",
            f"Wave {wave}: {name}",
            before_hp.get(key),
            after_hp.get(key),
            wave=wave,
            subject=name,
        )
    return tuple(changes)


def _maze_resource(record: VersionRecord) -> str:
    resources = _resource_ids(record, "maze")
    if len(resources) != 1:
        raise ValueError("混沌比较需要恰好一个混沌资源。")
    return resources[0]


def compare_maze_versions(
    version_one: str,
    version_two: str,
    node: int,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> HighModeDiffReport:
    if node < 1:
        raise ValueError("混沌比较需要提供正整数节点，例如 maze 1。")
    validate_request(record_one, record_two, version_one, version_two, "maze")
    resource_one = _maze_resource(record_one)
    resource_two = _maze_resource(record_two)
    nodes_one = available_maze_nodes(version_one, resource_one, data_root)
    nodes_two = available_maze_nodes(version_two, resource_two, data_root)
    if nodes_one != nodes_two:
        raise ValueError("两个版本必须拥有相同的混沌节点列表。")
    if node not in nodes_one:
        raise ValueError(f"混沌节点必须是 {nodes_one[0]} 到 {nodes_one[-1]}。")
    before = load_maze(version_one, resource_one, node, data_root).parts[0]
    after = load_maze(version_two, resource_two, node, data_root).parts[0]
    changes = _view_changes(before, after)
    return HighModeDiffReport(
        version_one,
        version_two,
        "maze",
        (HighModeSectionDiff(f"Maze {node}", "changed" if changes else "unchanged", changes),),
    )


def compare_all_maze_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[HighModeDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "maze")
    resource_one = _maze_resource(record_one)
    resource_two = _maze_resource(record_two)
    nodes_one = available_maze_nodes(version_one, resource_one, data_root)
    nodes_two = available_maze_nodes(version_two, resource_two, data_root)
    if nodes_one != nodes_two:
        raise ValueError("两个版本必须拥有相同的混沌节点列表。")
    return tuple(
        compare_maze_versions(
            version_one,
            version_two,
            node,
            record_one,
            record_two,
            data_root,
        )
        for node in nodes_one
    )


def _boss_effect_map(view: Any) -> dict[str, str]:
    return {buff.name: buff.description for buff in view.buffs}


def _boss_hp_text(view: Any) -> str:
    suffix = f" × {view.phases}" if view.phases > 1 else ""
    return f"HP {view.hp:,}{suffix}"


def _boss_changes(before: Any, after: Any) -> tuple[HighModeChange, ...]:
    changes: list[HighModeChange] = []

    def add(label: str, old: str | None, new: str | None) -> None:
        if old != new:
            kind = "added" if old is None else "removed" if new is None else "changed"
            changes.append(HighModeChange("metadata", label, old, new, kind, subject=label))

    add("名称", before.name, after.name)
    add("等级", str(before.level), str(after.level))
    add("阶段数", str(before.phases), str(after.phases))

    before_effects = _boss_effect_map(before)
    after_effects = _boss_effect_map(after)
    for name in sorted(set(before_effects) | set(after_effects)):
        old = before_effects.get(name)
        new = after_effects.get(name)
        if old != new:
            kind = "added" if old is None else "removed" if new is None else "changed"
            changes.append(HighModeChange("effects", name, old, new, kind, subject=name))

    old_hp = _boss_hp_text(before)
    new_hp = _boss_hp_text(after)
    if old_hp != new_hp:
        name = after.name or before.name
        changes.append(
            HighModeChange(
                "hp",
                f"Boss: {name}",
                old_hp,
                new_hp,
                "changed",
                wave=0,
                subject=name,
            )
        )
    return tuple(changes)


def compare_boss_versions(
    version_one: str,
    version_two: str,
    node: int,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> HighModeDiffReport:
    if node < 1:
        raise ValueError("末日比较需要提供正整数节点，例如 boss 1。")
    validate_request(record_one, record_two, version_one, version_two, "boss")
    resource_one = _resource_ids(record_one, "boss")
    resource_two = _resource_ids(record_two, "boss")
    if len(resource_one) != 1 or len(resource_two) != 1:
        raise ValueError("末日比较需要每个版本恰好一个末日资源。")
    before = load_boss(version_one, resource_one[0], node, data_root)
    after = load_boss(version_two, resource_two[0], node, data_root)
    changes = _boss_changes(before, after)
    return HighModeDiffReport(
        version_one,
        version_two,
        "boss",
        (HighModeSectionDiff(f"Boss {node}", "changed" if changes else "unchanged", changes),),
    )


def compare_all_boss_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[HighModeDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "boss")
    ids_one = _resource_ids(record_one, "boss")
    ids_two = _resource_ids(record_two, "boss")
    if len(ids_one) != 1 or len(ids_two) != 1:
        raise ValueError("末日比较需要每个版本恰好一个末日资源。")
    nodes_one = available_boss_nodes(version_one, ids_one[0], data_root)
    nodes_two = available_boss_nodes(version_two, ids_two[0], data_root)
    if nodes_one != nodes_two:
        raise ValueError("两个版本必须拥有相同的末日节点列表。")
    return tuple(
        compare_boss_versions(
            version_one,
            version_two,
            node,
            record_one,
            record_two,
            data_root,
        )
        for node in nodes_one
    )


def _peak_resource(record: VersionRecord) -> str:
    resources = _resource_ids(record, "peak")
    if len(resources) != 1:
        raise ValueError("异相比对需要恰好一个异相资源。")
    return resources[0]


def _story_resource(record: VersionRecord) -> str:
    resources = _resource_ids(record, "story")
    if len(resources) != 1:
        raise ValueError("虚构比较需要恰好一个虚构资源。")
    return resources[0]


def _story_nodes(
    version: str,
    record: VersionRecord,
    data_root: Path,
) -> tuple[int, ...]:
    payload = _read_json(
        _resource_path(data_root, version, "story", _story_resource(record))
    )
    if not isinstance(payload, dict):
        raise ValueError(f"版本 {version} 的虚构数据无效。")
    nodes: set[int] = set()
    has_default_node = False
    levels = payload.get("level")
    if isinstance(levels, list):
        for level in levels:
            if not isinstance(level, dict):
                continue
            for key in level:
                match = re.fullmatch(r"event_id_list(\d+)", str(key))
                if match:
                    nodes.add(int(match.group(1)))
                elif key == "event_id_list":
                    has_default_node = True
    if has_default_node:
        nodes.add(3 if nodes else 1)
    if not nodes:
        raise ValueError(f"版本 {version} 的虚构数据不包含可比较的节点。")
    return tuple(sorted(nodes))


def compare_highmode_versions(
    version_one: str,
    version_two: str,
    mode: str,
    node: int | None,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> HighModeDiffReport:
    if mode == "peak" or (mode == "knight" and node is None):
        if mode == "peak" and node is not None:
            raise ValueError("异相比对不接受节点参数，会比较所有异相分段。")
        validate_request(record_one, record_two, version_one, version_two, "peak")
        if mode == "knight":
            sections = (
                ("Knight 1", "knight", 1),
                ("Knight 2", "knight", 2),
                ("Knight 3", "knight", 3),
            )
        else:
            sections = (
                ("Knight 1", "knight", 1),
                ("Knight 2", "knight", 2),
                ("Knight 3", "knight", 3),
                ("King", "king", None),
                ("Hard-king", "hard-king", None),
            )
        resource_one = _peak_resource(record_one)
        resource_two = _peak_resource(record_two)
        section_reports = [
            _compare_peak_section(
                name,
                version_one,
                version_two,
                resource_one,
                resource_two,
                kind,
                section_node,
                data_root,
            )
            for name, kind, section_node in sections
        ]
        return HighModeDiffReport(version_one, version_two, mode, tuple(section_reports))

    if mode == "story":
        if node is None or node < 1:
            raise ValueError("虚构比较需要节点编号，例如 story 1。")
        validate_request(record_one, record_two, version_one, version_two, mode)
        before = load_story(version_one, _story_resource(record_one), node, data_root)
        after = load_story(version_two, _story_resource(record_two), node, data_root)
        changes = _view_changes(before, after)
        return HighModeDiffReport(
            version_one,
            version_two,
            f"story {node}",
            (HighModeSectionDiff(f"Story {node}", "changed" if changes else "unchanged", changes),),
        )

    if mode not in {"knight", "king", "hard-king"}:
        raise ValueError(f"高难度 diff 不支持模式 {mode!r}。")
    validate_request(record_one, record_two, version_one, version_two, "peak")
    resource_one = _peak_resource(record_one)
    resource_two = _peak_resource(record_two)
    if mode == "knight":
        if node not in (1, 2, 3):
            raise ValueError("骑士比较的节点必须是 1、2 或 3。")
        name = f"Knight {node}"
    else:
        if node is not None:
            raise ValueError(f"{_mode_label(mode)}比较不接受节点参数。")
        name = "King" if mode == "king" else "Hard-king"
    section = _compare_peak_section(
        name,
        version_one,
        version_two,
        resource_one,
        resource_two,
        mode,
        node,
        data_root,
    )
    return HighModeDiffReport(version_one, version_two, mode, (section,))


def _compare_peak_section(
    name: str,
    version_one: str,
    version_two: str,
    resource_one: str,
    resource_two: str,
    kind: str,
    node: int | None,
    data_root: Path,
) -> HighModeSectionDiff:
    before = load_peak(version_one, resource_one, kind, node, data_root)
    after = load_peak(version_two, resource_two, kind, node, data_root)
    changes = _view_changes(before, after)
    return HighModeSectionDiff(name, "changed" if changes else "unchanged", changes)


def compare_all_story_versions(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    data_root: Path = DATA_DIR,
) -> tuple[HighModeDiffReport, ...]:
    validate_request(record_one, record_two, version_one, version_two, "story")
    nodes_one = _story_nodes(version_one, record_one, data_root)
    nodes_two = _story_nodes(version_two, record_two, data_root)
    if nodes_one != nodes_two:
        raise ValueError("两个版本必须拥有相同的虚构节点列表。")
    return tuple(
        compare_highmode_versions(
            version_one,
            version_two,
            "story",
            node,
            record_one,
            record_two,
            data_root,
        )
        for node in nodes_one
    )

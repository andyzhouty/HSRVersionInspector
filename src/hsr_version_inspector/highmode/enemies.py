"""Enemy grouping and HP view assembly for high-mode loaders."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..boss import BossBuff, _load_monster
from ..scaling import calculate_hp, load_enemy_scaling
from .models import HighModeEnemy, HighModeView, HighModeWave

IGNORED_MONSTER_IDS = frozenset({8003060})


def _find_elite_group(
    level: dict[str, Any],
    monster_ids: tuple[int, ...],
    infinite_key: str = "infinite_list",
) -> int:
    groups = level.get(infinite_key, {})
    if not isinstance(groups, dict):
        return 1
    wave_ids = set(monster_ids)
    candidates: list[tuple[int, int]] = []
    for group in groups.values():
        if not isinstance(group, dict):
            continue
        group_ids = group.get("monster_group_id_list", [])
        if not isinstance(group_ids, list):
            continue
        if wave_ids.issubset(set(group_ids)):
            candidates.append((len(group_ids), int(group.get("elite_group", 1))))
    if candidates:
        return min(candidates)[1]
    return next(
        (
            int(group.get("elite_group", 1))
            for group in groups.values()
            if isinstance(group, dict)
        ),
        1,
    )

def _ordered_counts(monster_ids: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    counts = Counter(monster_id for monster_id in monster_ids if monster_id not in IGNORED_MONSTER_IDS)
    return tuple(counts.items())


def _profile_hp_multiplier(profile: dict[str, Any] | None) -> float | None:
    if not isinstance(profile, dict):
        return None
    params = profile.get("param_list")
    if not isinstance(params, list) or len(params) < 2:
        return None
    value = params[1]
    if not isinstance(value, (int, float)):
        return None
    return float(value) + 1


def _round_hp(value: float) -> int:
    return int(value + 0.5)


def _phase_ratios(monster: dict[str, Any]) -> tuple[float, ...]:
    phases = monster.get("phase_list")
    if not isinstance(phases, list):
        return ()
    return tuple(
        float(phase.get("phase_max_hp_ratio", 1))
        for phase in phases
        if isinstance(phase, dict) and isinstance(phase.get("phase_max_hp_ratio", 1), (int, float))
    )


def _child_for_id(monster: dict[str, Any], monster_id: int) -> dict[str, Any]:
    return next(
        (
            child
            for child in monster.get("child", [])
            if isinstance(child, dict) and child.get("id") == monster_id
        ),
        {},
    )


def _build_view(
    version: str,
    title: str,
    level_data: dict[str, Any],
    event: dict[str, Any],
    buffs: tuple[BossBuff, ...],
    recommended_elements: Any,
    data_root: Path,
    infinite_key: str = "infinite_list",
    wave_profiles: tuple[dict[str, Any], ...] = (),
    use_profile_hp_multiplier: bool = False,
    infinite_scaling: bool = True,
    season_buffs: tuple[BossBuff, ...] = (),
) -> HighModeView:
    hard_group = int(event.get("hard_level_group", 1))
    stage_level = int(event.get("level", 0))
    scaling = load_enemy_scaling(data_root)

    raw_waves = event.get("monster_list", [])
    if not isinstance(raw_waves, list):
        raise ValueError("关卡不包含敌人列表。")

    waves: list[HighModeWave] = []
    for number, raw_wave in enumerate(raw_waves, start=1):
        if not isinstance(raw_wave, dict):
            continue
        preview_ids = tuple(
            int(value)
            for value in raw_wave.values()
            if isinstance(value, (int, str)) and str(value).isdigit()
        )
        profile = wave_profiles[number - 1] if number <= len(wave_profiles) else None
        profile_ids = (
            tuple(int(value) for value in profile.get("monster_group_id_list", []))
            if isinstance(profile, dict)
            and isinstance(profile.get("monster_group_id_list"), list)
            else ()
        )
        monster_ids = profile_ids or preview_ids
        event_elite_group = event.get("elite_group")
        elite_group = (
            int(event_elite_group)
            if isinstance(event_elite_group, (int, str))
            and str(event_elite_group).isdigit()
            else _find_elite_group(level_data, monster_ids, infinite_key)
        )
        profile_multiplier = _profile_hp_multiplier(profile)
        enemies: list[HighModeEnemy] = []
        for monster_id, count in _ordered_counts(monster_ids):
            monster = _load_monster(data_root, version, monster_id)
            child = _child_for_id(monster, monster_id)
            base_hp = float(monster.get("hp_base", 0))
            child_ratio = float(child.get("hp_modify_ratio", 1))
            profile_hp_multiplier = (
                profile_multiplier - 1
                if use_profile_hp_multiplier and profile_multiplier is not None
                else None
            )
            primary_hp = calculate_hp(
                scaling,
                base_hp,
                child_ratio,
                hard_group,
                stage_level,
                elite_group,
                infinite=infinite_scaling,
                hp_multiplier=profile_hp_multiplier,
            )
            phase_hps = tuple(
                _round_hp(primary_hp * phase_ratio)
                for phase_ratio in _phase_ratios(monster)
            ) or (primary_hp,)
            enemies.append(
                HighModeEnemy(
                    name=str(monster.get("name", "未知敌人")),
                    hp=phase_hps[0],
                    count=count,
                    phase_hps=phase_hps,
                )
            )
        if enemies:
            waves.append(HighModeWave(number, stage_level, tuple(enemies)))

    if not waves:
        raise ValueError("关卡不包含敌人波次。")
    elements = (
        tuple(str(element) for element in recommended_elements)
        if isinstance(recommended_elements, list)
        else ()
    )
    phases = max(
        (len(enemy.phase_hps) for wave in waves for enemy in wave.enemies),
        default=1,
    )
    return HighModeView(
        version=version,
        title=title,
        level=stage_level,
        recommended_elements=elements,
        buffs=buffs,
        waves=tuple(waves),
        season_buffs=season_buffs,
        phases=phases,
    )

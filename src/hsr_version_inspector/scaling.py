from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_DIR_NAME = "config"
HARD_LEVEL_FILE = "HardLevelGroup.json"
ELITE_FILE = "EliteGroup.json"
INFINITE_ELITE_FILE = "InfiniteEliteGroup.json"


@dataclass(frozen=True)
class EnemyScaling:
    hard_level_hp: dict[tuple[int, int], float]
    elite_hp: dict[int, float]
    infinite_elite_hp: dict[int, float]


def _load_entries(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"缺少怪物倍率配置 {path}，请先运行 download-all。"
        ) from error
    if not isinstance(payload, list):
        raise ValueError(f"配置文件 {path} 应为 JSON 数组。")
    return [item for item in payload if isinstance(item, dict)]


def _value(entry: dict[str, Any], key: str) -> float:
    value = entry.get(key, {})
    if isinstance(value, dict):
        value = value.get("Value", 1)
    if not isinstance(value, (int, float)):
        raise ValueError(f"配置项 {key} 的倍率不是数字。")
    return float(value)


def load_enemy_scaling(data_root: Path) -> EnemyScaling:
    config_dir = data_root / CONFIG_DIR_NAME
    hard_level_hp = {
        (int(entry["HardLevelGroup"]), int(entry["Level"])): _value(entry, "HPRatio")
        for entry in _load_entries(config_dir / HARD_LEVEL_FILE)
        if "HardLevelGroup" in entry and "Level" in entry
    }
    elite_hp = {
        int(entry["EliteGroup"]): _value(entry, "HPRatio")
        for entry in _load_entries(config_dir / ELITE_FILE)
        if "EliteGroup" in entry
    }
    infinite_elite_hp = {
        int(entry["EliteGroup"]): _value(entry, "HPRatio")
        for entry in _load_entries(config_dir / INFINITE_ELITE_FILE)
        if "EliteGroup" in entry
    }
    return EnemyScaling(hard_level_hp, elite_hp, infinite_elite_hp)


def hard_level_hp_ratio(scaling: EnemyScaling, group: int, level: int) -> float:
    try:
        return scaling.hard_level_hp[(group, level)]
    except KeyError as error:
        raise ValueError(f"未找到高难度组 {group}、等级 {level} 的生命值系数。") from error


def _round_hp(value: float) -> int:
    return int(value + 0.5)


def calculate_hp(
    scaling: EnemyScaling,
    base_hp: float,
    base_modify_ratio: float,
    hard_level_group: int,
    level: int,
    elite_group: int,
    *,
    infinite: bool = False,
    hp_multiplier: float | None = None,
    round_up: bool = False,
) -> int:
    """Calculate an enemy's displayed HP from the game configuration tables.

    The source data applies the level table and the elite table independently:
    ``base_hp * hp_modify_ratio * HPRatio(level) * HPRatio(elite)``.
    ``hp_multiplier`` is only used for high-mode records whose stage data
    stores an explicit extra multiplier instead of an elite-group reference.
    Boss records use ``round_up`` because their source display rounds upward.
    """
    hard_ratio = hard_level_hp_ratio(scaling, hard_level_group, level)
    elite_ratios = (
        {**scaling.elite_hp, **scaling.infinite_elite_hp}
        if infinite
        else scaling.elite_hp
    )
    if hp_multiplier is not None:
        elite_ratio = 1 + hp_multiplier
    else:
        try:
            elite_ratio = elite_ratios[elite_group]
        except KeyError as error:
            table_name = "InfiniteEliteGroup" if infinite else "EliteGroup"
            raise ValueError(
                f"未找到 {table_name} {elite_group} 的生命值系数。"
            ) from error
    value = base_hp * base_modify_ratio * elite_ratio * hard_ratio
    return int(math.ceil(value)) if round_up else _round_hp(value)

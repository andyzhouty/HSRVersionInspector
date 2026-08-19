"""High-mode view models."""

from __future__ import annotations

from dataclasses import dataclass

from ..boss import BossBuff


@dataclass(frozen=True)
class HighModeEnemy:
    name: str
    hp: int
    count: int = 1
    phase_hps: tuple[int, ...] = ()


@dataclass(frozen=True)
class HighModeWave:
    number: int
    level: int
    enemies: tuple[HighModeEnemy, ...]


@dataclass(frozen=True)
class HighModeView:
    version: str
    title: str
    level: int
    recommended_elements: tuple[str, ...]
    buffs: tuple[BossBuff, ...]
    waves: tuple[HighModeWave, ...]
    season_buffs: tuple[BossBuff, ...] = ()
    phases: int = 1


@dataclass(frozen=True)
class MazeView:
    version: str
    node: int
    name: str
    parts: tuple[HighModeView, ...]

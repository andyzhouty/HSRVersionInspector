from __future__ import annotations

import json
from pathlib import Path


def write_scaling_config(root: Path) -> None:
    config = root / "config"
    config.mkdir(parents=True, exist_ok=True)
    hard_rows = [
        (1, 55, 37.432133),
        (1, 65, 73.85566),
        (1, 75, 121.49909),
        (1, 85, 188.2636),
        (1, 90, 236.53471),
        (3, 95, 375.4385),
        (3, 100, 484.69086),
        (3, 120, 1938.7634),
    ]
    (config / "HardLevelGroup.json").write_text(
        json.dumps(
            [
                {
                    "HardLevelGroup": group,
                    "Level": level,
                    "HPRatio": {"Value": ratio},
                }
                for group, level, ratio in hard_rows
            ]
        ),
        encoding="utf-8",
    )
    (config / "EliteGroup.json").write_text(
        json.dumps(
            [
                {"EliteGroup": group, "HPRatio": {"Value": ratio}}
                for group, ratio in ((1, 1), (89, 1.9), (90, 2), (367, 1))
            ]
        ),
        encoding="utf-8",
    )
    (config / "InfiniteEliteGroup.json").write_text(
        json.dumps(
            [
                {"EliteGroup": group, "HPRatio": {"Value": ratio}}
                for group, ratio in (
                    (1, 1),
                    (361, 6),
                    (367, 7.2),
                    (368, 6.8),
                    (369, 6.2),
                    (370, 8.6),
                )
            ]
        ),
        encoding="utf-8",
    )

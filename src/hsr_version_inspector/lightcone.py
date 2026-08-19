from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mappings import PATH_NAMES
from .paths import DATA_DIR

PLACEHOLDER = re.compile(r"#(\d+)\[(i|f(\d+))\](%)?")
TAG = re.compile(r"</?[^>]+>")
@dataclass(frozen=True)
class LightConeView:
    version: str
    lightcone_id: str
    name: str
    level: int
    rarity: int
    path: str
    hp: str
    attack: str
    defence: str
    refinement: str
    refinement_name: str
    description: str


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"文件 {path} 应为 JSON 对象。")
    return payload


def _format_number(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        if float(value).is_integer():
            return str(int(value))
        return f"{value:g}"
    return str(value)


def _format_parameter(value: Any, formatter: str, percent: bool) -> str:
    if not isinstance(value, (int, float)):
        return str(value)
    number = float(value) * 100 if percent else float(value)
    if formatter == "i":
        return _format_number(round(number) if percent else value)
    digits = int(formatter[1:])
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def _join_refinement_values(values: list[str]) -> str:
    if not values:
        return ""
    if all(value == values[0] for value in values[1:]):
        return values[0]
    return "/".join(values)


def _format_description(text: str, params_by_refinement: tuple[list[Any], ...]) -> str:
    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        values = []
        for params in params_by_refinement:
            if index >= len(params):
                return match.group(0)
            values.append(
                _format_parameter(
                    params[index],
                    match.group(2),
                    bool(match.group(4)),
                )
            )
        if match.group(4):
            return _join_refinement_values([f"{value}%" for value in values])
        return _join_refinement_values(values)

    rendered = PLACEHOLDER.sub(replace, text)
    return html.unescape(TAG.sub("", rendered)).replace(r"\n", "\n")


def _level_data(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    stats = payload.get("stats")
    if not isinstance(stats, list):
        raise ValueError("光锥数据不包含基础属性。")
    candidates = [
        item
        for item in stats
        if isinstance(item, dict) and str(item.get("max_level", "")).isdigit()
    ]
    if not candidates:
        raise ValueError("光锥数据不包含等级属性。")
    level_data = next(
        (item for item in candidates if int(item["max_level"]) == 80),
        max(candidates, key=lambda item: int(item["max_level"])),
    )
    return int(level_data["max_level"]), level_data


def _rarity(value: Any) -> int:
    match = re.search(r"(\d+)$", str(value))
    return int(match.group(1)) if match else 0


def _refinement_data(payload: dict[str, Any]) -> tuple[str, str, str]:
    refinements = payload.get("refinements")
    if not isinstance(refinements, dict):
        raise ValueError("光锥数据不包含叠影效果。")
    levels = refinements.get("level")
    if not isinstance(levels, dict):
        raise ValueError("光锥数据不包含叠影等级。")
    ordered = tuple(
        value
        for _, value in sorted(levels.items(), key=lambda item: int(item[0]))
        if isinstance(value, dict) and isinstance(value.get("param_list"), list)
    )
    if not ordered:
        raise ValueError("光锥数据不包含叠影参数。")
    description = _format_description(
        str(refinements.get("desc") or ""),
        tuple(value["param_list"] for value in ordered),
    )
    refinement = "/".join(str(index) for index in range(1, len(ordered) + 1))
    return refinement, str(refinements.get("name") or "光锥效果"), description


def load_lightcone(
    version: str,
    lightcone_id: str,
    data_root: Path = DATA_DIR,
) -> LightConeView:
    path = data_root / version / "zh" / "lightcone" / f"{lightcone_id}.json"
    payload = _load_json(path)
    level, stats = _level_data(payload)
    refinement, refinement_name, description = _refinement_data(payload)
    return LightConeView(
        version=version,
        lightcone_id=lightcone_id,
        name=str(payload.get("name", lightcone_id)),
        level=level,
        rarity=_rarity(payload.get("rarity")),
        path=PATH_NAMES.get(str(payload.get("base_type", "")), str(payload.get("base_type", "未知"))),
        hp=_format_stat(stats.get("base_hp", 0), stats.get("base_hp_add", 0), level),
        attack=_format_stat(
            stats.get("base_attack", 0),
            stats.get("base_attack_add", 0),
            level,
        ),
        defence=_format_stat(
            stats.get("base_defence", 0),
            stats.get("base_defence_add", 0),
            level,
        ),
        refinement=refinement,
        refinement_name=refinement_name,
        description=description,
    )


def _format_stat(value: Any, increment: Any, level: int) -> str:
    if not isinstance(value, (int, float)):
        return str(value)
    if not isinstance(increment, (int, float)):
        increment = 0
    return f"{float(value) + float(increment) * (level - 1):.2f}"

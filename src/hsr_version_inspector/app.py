from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sys
from typing import Any

import typer
from typer import rich_utils
from rich import box
from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .boss import BossBuff, BossView, available_boss_nodes, load_boss
from .character import (
    CharacterSkill,
    CharacterText,
    CharacterView,
    group_skill_entries,
    load_character,
    skill_entry_title,
    skill_group_title,
)
from .data import FullCatalog, VersionRecord, find_release, latest_release, load_catalog, load_full_catalog
from .diff import (
    DiffReport,
    CharacterChange,
    CharacterDiffReport,
    HighModeChange,
    HighModeDiffReport,
    LightConeChange,
    LightConeDiffReport,
    compare_all_boss_versions,
    compare_highmode_versions,
    compare_all_character_versions,
    compare_boss_versions,
    compare_character_versions,
    compare_all_lightcone_versions,
    compare_all_maze_versions,
    compare_all_story_versions,
    compare_lightcone_versions,
    compare_maze_versions,
    compare_versions,
    character_change_subject,
    format_name_change,
    format_value,
    is_missing,
    supported_modes_text,
    highmode_change_subject,
    highmode_change_wave,
    tokenize_text_diff,
    tokenize_refinement_diff,
)
from .download import cleanup_data, download_all
from .highmode import (
    HighModeView,
    MazeView,
    available_maze_nodes,
    available_story_nodes,
    load_maze,
    load_peak,
    load_story,
)
from .lightcone import LightConeView, load_lightcone
from .pdf import PdfRenderer
from .paths import DATA_DIR


rich_utils.ARGUMENTS_PANEL_TITLE = "参数"
rich_utils.COMMANDS_PANEL_TITLE = "命令"
rich_utils.ERRORS_PANEL_TITLE = "错误"
rich_utils.OPTIONS_PANEL_TITLE = "选项"
rich_utils.REQUIRED_LONG_STRING = "[必填]"

try:
    from typer._click import decorators as _typer_decorators
    from typer._click.formatting import HelpFormatter as _TyperHelpFormatter

    _default_help_option = _typer_decorators.help_option

    def _chinese_help_option(param_decls: list[str]):
        decorator = _default_help_option(param_decls)

        def apply_help_option(command):
            result = decorator(command)
            result.params[-1].help = "显示帮助信息并退出。"
            return result

        return apply_help_option

    _typer_decorators.help_option = _chinese_help_option
    _default_write_usage = _TyperHelpFormatter.write_usage

    def _write_chinese_usage(self, prog: str, args: str = "", prefix: str | None = None):
        return _default_write_usage(self, prog, args, prefix or "用法：")

    _TyperHelpFormatter.write_usage = _write_chinese_usage
except ImportError:  # pragma: no cover - depends on Typer's bundled Click layer
    pass


app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    subcommand_metavar="命令 [参数]...",
    options_metavar="[选项]",
    help="在终端浏览《崩坏：星穹铁道》版本数据。",
)
console = Console()
MARKDOWN_OUTPUT = False
PDF_OUTPUT = False
PDF_RENDERER: PdfRenderer | None = None
BATCH_PEAK_SECTIONS = (
    ("knight", 1),
    ("knight", 2),
    ("knight", 3),
    ("king", None),
    ("hard-king", None),
)
MODE_LABELS = {
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
STATUS_LABELS = {
    "added": "新增",
    "removed": "删除",
    "changed": "已变更",
    "unchanged": "未变更",
    "missing": "缺失",
}
ELEMENT_LABELS = {
    "Physical": "物理",
    "Fire": "火",
    "Ice": "冰",
    "Lightning": "雷",
    "Thunder": "雷",
    "Wind": "风",
    "Quantum": "量子",
    "Imaginary": "虚数",
}


def _mode_label(mode: str) -> str:
    if mode.startswith("story "):
        return f"虚构节点 {mode.removeprefix('story ')}"
    return MODE_LABELS.get(mode, mode)


def _element_label(element: str) -> str:
    return ELEMENT_LABELS.get(element, element)


def _terminal_text(value: object) -> str:
    """Render multiplication asterisks as the mathematical sign in the CLI."""
    return str(value).replace("*", "×")


def _markdown_text(value: object) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("*", "\\*")
        .replace("_", "\\_")
    )


def _markdown_cell(value: object) -> str:
    return _markdown_text(value).replace("|", "\\|").replace("\n", "<br>")


def _print_markdown(lines: list[str]) -> None:
    sys.stdout.write("\n".join(lines).rstrip() + "\n")


def _print_no_changes() -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_no_changes()
    elif MARKDOWN_OUTPUT:
        _print_markdown(["未发现变更。"])
    else:
        console.print("[dim]未发现变更。[/dim]")


def _enemy_count_text(count: int) -> str:
    return f"×{count}"


def _markdown_enemy_count_text(count: int) -> str:
    return f"*{count}"


def _unique_buffs(buffs: tuple[BossBuff, ...], seen: set[tuple[str, str]]) -> tuple[BossBuff, ...]:
    unique: list[BossBuff] = []
    for buff in buffs:
        key = (buff.name, buff.description)
        if key in seen:
            continue
        seen.add(key)
        unique.append(buff)
    return tuple(unique)


def _write_pdf() -> None:
    if PDF_RENDERER is None:
        raise RuntimeError("PDF 渲染器未初始化。")
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        raise RuntimeError("PDF 输出需要二进制标准输出。")
    stream.write(PDF_RENDERER.build())
    stream.flush()


@contextmanager
def _terminal_output():
    """Keep interactive navigation on Rich terminal output."""
    global MARKDOWN_OUTPUT
    previous_markdown = MARKDOWN_OUTPUT
    MARKDOWN_OUTPUT = False
    try:
        yield
    finally:
        MARKDOWN_OUTPUT = previous_markdown


def _markdown_table(
    headers: tuple[str, ...],
    rows: list[tuple[object, ...]],
    *,
    markup_rows: bool = False,
) -> list[str]:
    cell = _markdown_markup_cell if markup_rows else _markdown_cell
    lines = [
        "| " + " | ".join(_markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(cell(value) for value in row) + " |"
        for row in rows
    )
    return lines


def _markdown_markup_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _rich_markup_to_markdown(value: str) -> str:
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


def _markdown_catalog(catalog: tuple[VersionRecord, ...]) -> list[str]:
    lines = ["# 星穹铁道版本检查器", ""]
    lines.extend(
        _markdown_table(
            ("版本组", "版本数", "角色", "光锥", "虚构", "末日"),
            [
                (
                    record.name,
                    len(record.versions),
                    len(record.character),
                    len(record.lightcone),
                    record.story or "-",
                    record.boss or "-",
                )
                for record in catalog
            ],
        )
    )
    lines.extend(
        [
            "",
            f"共 {len(catalog)} 个版本组，追踪 "
            f"{sum(record.content_count for record in catalog)} 个数据项。",
        ]
    )
    return lines


def _markdown_buffs(lines: list[str], title: str, buffs: tuple) -> None:
    if not buffs:
        return
    lines.extend(["", f"## {_markdown_text(title)}"])
    for buff in buffs:
        lines.extend(
            [
                "",
                f"### {_markdown_text(buff.name)}",
                _markdown_text(buff.description),
            ]
        )


def _markdown_character(view: CharacterView, verbose: bool) -> list[str]:
    lines = [f"# {_markdown_text(view.name)}", ""]
    summary = [("等级", f"{view.level}级"), ("角色编号", view.character_id)]
    if view.base_stats:
        summary.extend(
            [
                ("基础生命值", view.base_stats.hp),
                ("基础攻击力", view.base_stats.attack),
                ("基础防御力", view.base_stats.defence),
                ("基础速度", view.base_stats.speed),
            ]
        )
    lines.extend(_markdown_table(("属性", "数值"), summary))

    def add_skills(title: str, entries: tuple[CharacterSkill, ...]) -> None:
        if not entries:
            return
        lines.extend(["", f"## {_markdown_text(title)}"])
        for group in group_skill_entries(entries):
            lines.extend(["", f"### {_markdown_text(skill_group_title(group))}"])
            for index, entry in enumerate(group):
                if index:
                    lines.extend(["", "---"])
                lines.extend(
                    [
                        "",
                        f"#### {_markdown_text(skill_entry_title(group, entry))}",
                        _markdown_text(entry.description),
                    ]
                )

    def add_texts(title: str, entries: tuple[CharacterText, ...]) -> None:
        if not entries:
            return
        lines.extend(["", f"## {_markdown_text(title)}"])
        for entry in entries:
            lines.extend(
                [
                    "",
                    f"### {_markdown_text(entry.name)}",
                    _markdown_text(entry.description),
                ]
            )

    add_skills("技能", view.skills)
    if view.memosprite_name:
        add_skills(f"忆灵 · {view.memosprite_name}", view.memosprite_skills)
    add_texts("行迹", view.traces)
    if view.trace_stats:
        lines.extend(["", "### 行迹属性"])
        lines.extend(
            _markdown_table(
                tuple(stat.name for stat in view.trace_stats),
                [tuple(stat.description for stat in view.trace_stats)],
            )
        )
    if verbose:
        add_texts("特殊效果", view.special_effects)
    add_texts("星魂", view.eidolons)
    return lines


def _markdown_lightcone(view: LightConeView) -> list[str]:
    lines = [f"# {_markdown_text(view.name)}", ""]
    lines.extend(
        _markdown_table(
            ("属性", "数值"),
            [
                ("等级", f"{view.level}级"),
                ("稀有度", f"{view.rarity}星"),
                ("命途", view.path),
                ("生命值", view.hp),
                ("攻击力", view.attack),
                ("防御力", view.defence),
                ("叠影", view.refinement),
            ],
        )
    )
    lines.extend(
        [
            "",
            "## 光锥效果",
            "",
            f"### {_markdown_text(view.refinement_name)}",
            _markdown_text(view.description),
        ]
    )
    return lines


def _markdown_boss(view: BossView, title: str | None) -> list[str]:
    lines = [f"# {_markdown_text(title or view.name)}", ""]
    hp = f"{view.hp:,}" if view.phases <= 1 else f"{view.hp:,} × {view.phases}"
    lines.extend(
        _markdown_table(
            ("属性", "数值"),
            [
                ("首领", view.name),
                ("等级", f"{view.level}级"),
                ("生命值", hp),
            ],
        )
    )
    _markdown_buffs(lines, "增益效果", view.buffs)
    return lines


def _markdown_highmode(
    view: HighModeView,
    title: str | None = None,
    stage_buffs: tuple[BossBuff, ...] | None = None,
    prelude_buffs: tuple[BossBuff, ...] | None = None,
) -> list[str]:
    lines: list[str] = []
    if prelude_buffs:
        _markdown_buffs(lines, "虚构效果", prelude_buffs)
    lines.extend([f"# {_markdown_text(title or view.title)}", ""])
    summary = [("等级", f"{view.level}级")]
    summary.append(
        (
            "推荐元素",
            ", ".join(_element_label(element) for element in view.recommended_elements)
            or "无",
        )
    )
    if view.phases > 1:
        summary.append(("阶段数", view.phases))
    lines.extend(_markdown_table(("属性", "数值"), summary))
    if prelude_buffs is None:
        _markdown_buffs(lines, "赛季效果", view.season_buffs)
    _markdown_buffs(lines, "关卡效果", view.buffs if stage_buffs is None else stage_buffs)
    lines.extend(["", "## 敌人波次"])
    for wave in view.waves:
        lines.extend(["", f"### 第 {wave.number} 波 · 等级 {wave.level}"])
        wave_phases = max((len(enemy.phase_hps) for enemy in wave.enemies), default=1)
        same_phase_hp = wave_phases > 1 and all(
            len(enemy.phase_hps) == wave_phases
            and len(set(enemy.phase_hps)) == 1
            for enemy in wave.enemies
        )
        if wave_phases > 1 and not same_phase_hp:
            headers = ("敌人", "数量", *tuple(f"P{phase}" for phase in range(1, wave_phases + 1)))
        else:
            headers = ("敌人", "数量", "生命值")
        rows: list[tuple[object, ...]] = []
        for enemy in wave.enemies:
            if same_phase_hp:
                hp_values: tuple[object, ...] = (f"{enemy.phase_hps[0]:,} × {wave_phases}",)
            elif wave_phases > 1:
                hp_values = tuple(f"{value:,}" for value in enemy.phase_hps[:wave_phases])
            else:
                hp_values = (f"{enemy.hp:,}",)
            rows.append((enemy.name, _markdown_enemy_count_text(enemy.count), *hp_values))
        lines.extend(_markdown_table(headers, rows))
    return lines


def _markdown_character_change(change: CharacterChange) -> str:
    if change.kind == "added":
        return f"新增：{_markdown_text(change.after or '')}"
    if change.kind == "removed":
        return f"删除：{_markdown_text(change.before or '')}"
    return _rich_markup_to_markdown(
        _markdown_shared_text_markup(change.before or "", change.after or "")
    )


def _markdown_base_change(change: CharacterChange | LightConeChange) -> str:
    label = _markdown_text(change.label)
    if change.kind == "added":
        return f"{label}：新增：{_markdown_text(change.after or '')}"
    if change.kind == "removed":
        return f"{label}：删除：{_markdown_text(change.before or '')}"
    return (
        f"{label}：~~{_markdown_text(change.before or '')}~~ "
        f"{_markdown_text(change.after or '')}"
    )


def _markdown_base_change_value(change: CharacterChange | LightConeChange) -> str:
    if change.kind == "added":
        return f"新增：{_markdown_text(change.after or '')}"
    if change.kind == "removed":
        return f"删除：{_markdown_text(change.before or '')}"
    return (
        f"~~{_markdown_text(change.before or '')}~~ "
        f"{_markdown_text(change.after or '')}"
    )


def _markdown_lightcone_change(change: LightConeChange) -> str:
    if change.kind == "added":
        return f"新增：{_markdown_text(change.after or '')}"
    if change.kind == "removed":
        return f"删除：{_markdown_text(change.before or '')}"
    return _rich_markup_to_markdown(
        _markdown_lightcone_text_markup(change.before or "", change.after or "")
    )


def _markdown_json_change(change: Any) -> str:
    if is_missing(change.before):
        return f"新增：{_markdown_text(format_value(change.after))}"
    if is_missing(change.after):
        return f"删除：{_markdown_text(format_value(change.before))}"
    return (
        f"~~{_markdown_text(format_value(change.before))}~~ "
        f"{_markdown_text(format_value(change.after))}"
    )


def _markdown_diff(report: DiffReport) -> list[str]:
    changed = report.changed_resources
    lines = ["# 数据差异", ""]
    lines.extend(_markdown_table(
        ("版本", "模式", "变更资源数"),
        [(f"{report.version_one} → {report.version_two}", _mode_label(report.mode), len(changed))],
    ))
    if not changed:
        lines.extend(["", "未发现变更。"])
        return lines
    lines.extend(["", "## 资源概览", ""])
    lines.extend(
        _markdown_table(
            ("资源", "状态", "变更数"),
            [
                (resource.resource_id, STATUS_LABELS.get(resource.status, resource.status), resource.change_count)
                for resource in changed
            ],
        )
    )
    for resource in changed:
        lines.extend(["", f"## {_markdown_text(_mode_label(report.mode))}/{resource.resource_id}.json"])
        lines.extend(
            _markdown_table(
                ("路径", "变更"),
                [(_markdown_text(change.path), _markdown_json_change(change)) for change in resource.changes],
                markup_rows=True,
            )
        )
    return lines


def _markdown_character_diff(report: CharacterDiffReport, verbose: bool) -> list[str]:
    sections = tuple(
        section
        for section in report.sections
        if verbose or section.name != "特殊效果"
    )
    changed_sections = tuple(section for section in sections if section.status != "unchanged")
    lines = [
        "# 角色差异",
        "",
    ]
    lines.extend(_markdown_table(
        ("版本", "角色", "变更分类数"),
        [(
            f"{report.version_one} → {report.version_two}",
            _markdown_text(format_name_change(report.name_one, report.name_two)),
            len(changed_sections),
        )],
    ))
    if not changed_sections:
        lines.extend(["", "未发现变更。"])
        return lines
    lines.extend(["", "## 变更分类", ""])
    lines.extend(
        _markdown_table(
            ("分类", "状态", "变更数"),
            [(section.name, STATUS_LABELS["changed"], len(section.changes)) for section in changed_sections],
        )
    )
    for section in changed_sections:
        lines.extend(["", f"## {_markdown_text(section.name)}"])
        if section.name == "基础属性":
            lines.extend(_markdown_table(
                tuple(_markdown_text(change.label) for change in section.changes),
                [[
                    _markdown_base_change_value(change)
                    for change in section.changes
                ]],
                markup_rows=True,
            ))
            continue
        rows = []
        for change in sorted(section.changes, key=_character_change_sort_key):
            rows.append((
                _markdown_text(character_change_subject(section.name, change)),
                _markdown_character_change(change),
            ))
        lines.extend(_markdown_table(("项目", "变更"), rows, markup_rows=True))
    return lines


def _markdown_lightcone_diff(report: LightConeDiffReport) -> list[str]:
    changed_sections = tuple(section for section in report.sections if section.status != "unchanged")
    lines = [
        "# 光锥差异",
        "",
    ]
    lines.extend(_markdown_table(
        ("版本", "光锥", "变更分类数"),
        [(
            f"{report.version_one} → {report.version_two}",
            _markdown_text(format_name_change(report.name_one, report.name_two)),
            len(changed_sections),
        )],
    ))
    if not changed_sections:
        lines.extend(["", "未发现变更。"])
        return lines
    lines.extend(["", "## 变更分类", ""])
    lines.extend(
        _markdown_table(
            ("分类", "状态", "变更数"),
            [(section.name, STATUS_LABELS["changed"], len(section.changes)) for section in changed_sections],
        )
    )
    for section in changed_sections:
        lines.extend(["", f"## {_markdown_text(section.name)}"])
        rows = []
        for change in sorted(section.changes, key=_lightcone_change_sort_key):
            value = (
                _markdown_base_change_value(change)
                if section.name == "基础属性"
                else _markdown_lightcone_change(change)
            )
            rows.append((_markdown_text(change.label), value))
        lines.extend(_markdown_table(("项目", "变更"), rows, markup_rows=True))
    return lines


def _markdown_highmode_change(change: HighModeChange) -> str:
    if change.kind == "added":
        return f"新增：{_markdown_text(change.after or '')}"
    if change.kind == "removed":
        return f"删除：{_markdown_text(change.before or '')}"
    if change.category == "hp":
        return _rich_markup_to_markdown(
            _rich_text_diff_markup(
                change.before or "",
                change.after or "",
                arrow=True,
                whole=True,
            )
        )
    return _rich_markup_to_markdown(
        _markdown_shared_text_arrow_markup(change.before or "", change.after or "")
    )


def _markdown_highmode_diff(
    report: HighModeDiffReport,
    include_header: bool = True,
) -> list[str]:
    changed_sections = report.changed_sections
    lines: list[str] = []
    if include_header:
        lines.extend([
            f"# {_markdown_text(_mode_label(report.mode))}差异",
            "",
        ])
        lines.extend(_markdown_table(
            ("版本", "模式"),
            [(f"{report.version_one} → {report.version_two}", _mode_label(report.mode))],
        ))
    if not changed_sections:
        lines.extend(["", "未发现变更。"])
        return lines
    for section in changed_sections:
        lines.extend(["", f"## {_markdown_text(_highmode_section_label(section.name))}"])
        effect_changes = tuple(change for change in section.changes if change.category == "effects")
        if effect_changes:
            lines.extend(["", "### 关卡效果"])
            lines.extend(
                _markdown_table(
                    ("效果", "变更"),
                    [
                        (_markdown_text(highmode_change_subject(change)), _markdown_highmode_change(change))
                        for change in sorted(effect_changes, key=_highmode_change_sort_key)
                    ],
                    markup_rows=True,
                )
            )
        hp_changes = tuple(change for change in section.changes if change.category == "hp")
        if hp_changes:
            lines.extend(["", "### 生命值"])
            waves: dict[int, list[HighModeChange]] = {}
            for change in hp_changes:
                wave = highmode_change_wave(change) or 0
                waves.setdefault(wave, []).append(change)
            for wave, changes in waves.items():
                wave_label = "首领" if wave == 0 else f"第 {wave} 波"
                lines.extend(["", f"#### {wave_label}"])
                lines.extend(
                    _markdown_table(
                        ("敌人", "变更"),
                        [
                            (_markdown_text(highmode_change_subject(change)), _markdown_highmode_change(change))
                            for change in sorted(changes, key=_highmode_change_sort_key)
                        ],
                        markup_rows=True,
                    )
                )
        metadata_changes = tuple(change for change in section.changes if change.category == "metadata")
        if metadata_changes:
            lines.extend(["", "### 基本信息"])
            lines.extend(
                _markdown_table(
                    ("项目", "变更"),
                    [
                        (_markdown_text(_highmode_metadata_label(change.label)), _markdown_highmode_change(change))
                        for change in sorted(metadata_changes, key=_highmode_change_sort_key)
                    ],
                    markup_rows=True,
                )
            )
    return lines


def _abort_cli(message: object) -> None:
    console.print(f"[red]错误：{message}[/red]")
    raise typer.Exit(code=1)


def _highmode_section_label(name: str) -> str:
    label = {
        "Knight 1": "骑士 1",
        "Knight 2": "骑士 2",
        "Knight 3": "骑士 3",
        "King": "王棋",
        "Hard-king": "绝境",
    }.get(name)
    if label:
        return label
    match = re.fullmatch(r"Story (\d+)", name)
    if match:
        return f"虚构节点 {match.group(1)}"
    match = re.fullmatch(r"Maze (\d+)", name)
    if match:
        return f"混沌节点 {match.group(1)}"
    match = re.fullmatch(r"Boss (\d+)", name)
    return f"末日节点 {match.group(1)}" if match else name


def _highmode_wave_label(label: str) -> str:
    match = re.fullmatch(r"Wave (\d+)", label)
    return f"第 {match.group(1)} 波" if match else label


def _highmode_metadata_label(label: str) -> str:
    return {"Title": "名称", "Level": "等级"}.get(label, label)


def catalog_table(
    catalog: tuple[VersionRecord, ...],
    numbered: bool = False,
) -> Table:
    table = Table(title="星穹铁道版本检查器", header_style="bold cyan")
    if numbered:
        table.add_column("编号", justify="right", style="bold yellow", no_wrap=True, overflow="fold")
    table.add_column("版本组", style="bold", overflow="fold")
    table.add_column("版本数", overflow="fold")
    table.add_column("角色", justify="right", overflow="fold")
    table.add_column("光锥", justify="right", overflow="fold")
    table.add_column("虚构", justify="right", overflow="fold")
    table.add_column("末日", justify="right", overflow="fold")
    for index, record in enumerate(catalog, start=1):
        row = [
            record.name,
            str(len(record.versions)),
            str(len(record.character)),
            str(len(record.lightcone)),
            record.story or "-",
            record.boss or "-",
        ]
        if numbered:
            row.insert(0, str(index))
        table.add_row(*row)
    return table


def detail_panel(record: VersionRecord) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(overflow="fold")
    table.add_row("版本列表", ", ".join(record.versions) or "-")
    table.add_row("角色数据", ", ".join(record.character) or "-")
    table.add_row("光锥数据", ", ".join(record.lightcone) or "-")
    table.add_row("混沌数据", record.maze or "-")
    table.add_row("虚构数据", record.story or "-")
    table.add_row("末日数据", record.boss or "-")
    table.add_row("异相数据", record.peak or "-")
    return Panel(table, title=f"版本 {record.name}", border_style="cyan")


def render_catalog(catalog: tuple[VersionRecord, ...]) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_catalog(catalog)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(_markdown_catalog(catalog))
        return
    console.print(catalog_table(catalog))
    console.print(
        f"[dim]共 {len(catalog)} 个版本组，"
        f"追踪 {sum(record.content_count for record in catalog)} 个数据项[/dim]"
    )


def _raw_resource_path(version: str, mode: str, resource_id: str) -> Path:
    return DATA_DIR / version / "zh" / mode / f"{resource_id}.json"


def _load_raw_resource(
    version: str,
    mode: str,
    resource_id: str,
) -> object | None:
    path = _raw_resource_path(version, mode, resource_id)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _markdown_raw_resource(
    version: str,
    mode: str,
    resource_id: str,
    payload: object | None,
) -> list[str]:
    lines = [f"# {_markdown_text(_mode_label(mode))}", "", f"- 版本：{version}", f"- 资源编号：{resource_id}"]
    if payload is None:
        lines.extend(["", f"未找到本地数据：{_raw_resource_path(version, mode, resource_id)}。", "请先运行 `hvi download`。"])
        return lines
    lines.extend(["", "```json", json.dumps(payload, ensure_ascii=False, indent=2), "```"])
    return lines


def render_raw_resource(
    version: str,
    mode: str,
    resource_id: str,
    payload: object | None,
) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_raw_resource(version, mode, resource_id, payload)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(_markdown_raw_resource(version, mode, resource_id, payload))
        return
    if payload is None:
        body = (
            f"未找到本地数据：{_raw_resource_path(version, mode, resource_id)}。\n"
            "请先运行 hvi download。"
        )
    else:
        body = json.dumps(payload, ensure_ascii=False, indent=2)
    console.print(Panel(body, title=f"{_mode_label(mode)} · {resource_id}", border_style="cyan"))


def render_batch_error(title: str, error: object) -> None:
    message = f"读取失败：{error}"
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_error(title, message)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown([f"# {_markdown_text(title)}", "", _markdown_text(message)])
        return
    console.print(Panel(message, title=title, border_style="red"))


def render_boss(view: BossView, title: str | None = None) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_boss(view, title)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(_markdown_boss(view, title))
        return
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", no_wrap=True)
    summary.add_column(overflow="fold")
    summary.add_row("首领", view.name)
    summary.add_row("等级", f"{view.level}级")
    hp = f"{view.hp:,}" if view.phases <= 1 else f"{view.hp:,} × {view.phases}"
    summary.add_row("生命值", hp)
    console.print(Panel(summary, title=title or view.name, border_style="cyan"))
    console.print("[bold cyan]增益效果[/bold cyan]")
    for buff in view.buffs:
        console.print(
            Panel(
                f"[bold]{_terminal_text(buff.name)}[/bold]\n{_terminal_text(buff.description)}",
                border_style="magenta",
            )
            )


def render_character(view: CharacterView, verbose: bool = False) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_character(view, verbose)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(_markdown_character(view, verbose))
        return
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", no_wrap=True)
    summary.add_column(overflow="fold")
    summary.add_row("等级", f"{view.level}级")
    summary.add_row("角色编号", view.character_id)
    if view.base_stats:
        summary.add_row("基础生命值", view.base_stats.hp)
        summary.add_row("基础攻击力", view.base_stats.attack)
        summary.add_row("基础防御力", view.base_stats.defence)
        summary.add_row("基础速度", view.base_stats.speed)
    console.print(Panel(summary, title=view.name, border_style="cyan"))

    def render_entries(title: str, entries: tuple[CharacterSkill, ...]) -> None:
        if not entries:
            return
        console.print(f"[bold cyan]{title}[/bold cyan]")
        for group in group_skill_entries(entries):
            body_parts: list[Text | Rule] = []
            for index, entry in enumerate(group):
                if index:
                    body_parts.append(Rule(style="magenta"))
                heading = (
                    f"[bold]{escape(_terminal_text(skill_entry_title(group, entry)))}[/bold]"
                )
                body_parts.append(
                    Text.from_markup(
                        f"{heading}\n{escape(_terminal_text(entry.description))}"
                    )
                )
            console.print(
                Panel(
                    Group(*body_parts),
                    title=escape(skill_group_title(group)),
                    border_style="magenta",
                )
            )

    def render_text_entries(entries: tuple[CharacterText, ...]) -> None:
        for entry in entries:
            console.print(
                Panel(
                    f"[bold]{escape(_terminal_text(entry.name))}[/bold]\n"
                    f"{escape(_terminal_text(entry.description))}",
                    border_style="magenta",
                )
            )

    def render_texts(title: str, entries: tuple[CharacterText, ...]) -> None:
        if entries:
            console.print(f"[bold cyan]{title}[/bold cyan]")
            render_text_entries(entries)

    render_entries("技能", view.skills)
    if view.memosprite_name:
        render_entries(f"忆灵 · {view.memosprite_name}", view.memosprite_skills)
    if view.traces or view.trace_stats:
        console.print("[bold cyan]行迹[/bold cyan]")
        render_text_entries(view.traces)
        if view.trace_stats:
            table = Table(show_header=False, padding=(0, 2), box=box.SQUARE)
            for _ in view.trace_stats:
                table.add_column(justify="right", overflow="fold")
            table.add_row(
                *(f"[bold]{escape(stat.name)}[/bold]" for stat in view.trace_stats)
            )
            table.add_row(
                *(escape(_terminal_text(stat.description)) for stat in view.trace_stats)
            )
            console.print(table)
    if verbose:
        render_texts("特殊效果", view.special_effects)
    render_texts("星魂", view.eidolons)


def render_lightcone(view: LightConeView) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_lightcone(view)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(_markdown_lightcone(view))
        return
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", no_wrap=True)
    summary.add_column(overflow="fold")
    summary.add_row("等级", f"{view.level}级")
    summary.add_row("稀有度", f"{view.rarity}星")
    summary.add_row("命途", view.path)
    summary.add_row("生命值", view.hp)
    summary.add_row("攻击力", view.attack)
    summary.add_row("防御力", view.defence)
    summary.add_row("叠影", str(view.refinement))
    console.print(Panel(summary, title=view.name, border_style="cyan"))
    console.print("[bold cyan]光锥效果[/bold cyan]")
    console.print(
        Panel(
            f"[bold]{_terminal_text(view.refinement_name)}[/bold]\n"
            f"{_terminal_text(view.description)}",
            border_style="magenta",
        )
    )


def render_highmode(
    view: HighModeView,
    title: str | None = None,
    stage_buffs: tuple[BossBuff, ...] | None = None,
    prelude_buffs: tuple[BossBuff, ...] | None = None,
) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_highmode(
            view,
            title=title,
            stage_buffs=stage_buffs,
            prelude_buffs=prelude_buffs,
        )
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(
            _markdown_highmode(
                view,
                title=title,
                stage_buffs=stage_buffs,
                prelude_buffs=prelude_buffs,
            )
        )
        return

    def render_buffs(title: str, buffs: tuple) -> None:
        console.print(f"[bold cyan]{title}[/bold cyan]")
        if not buffs:
            console.print("[dim]无[/dim]")
        for buff in buffs:
            console.print(
                Panel(
                    f"[bold]{_terminal_text(buff.name)}[/bold]\n"
                    f"{_terminal_text(buff.description)}",
                    border_style="magenta",
                )
            )

    if prelude_buffs:
        render_buffs("虚构效果", prelude_buffs)
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", no_wrap=True)
    summary.add_column(overflow="fold")
    summary.add_row("等级", f"{view.level}级")
    summary.add_row(
        "推荐元素",
        ", ".join(_element_label(element) for element in view.recommended_elements) or "无",
    )
    if view.phases > 1:
        summary.add_row("阶段数", str(view.phases))
    console.print(Panel(summary, title=title or view.title, border_style="cyan"))

    if prelude_buffs is None and view.season_buffs:
        render_buffs("赛季效果", view.season_buffs)
    if stage_buffs is None:
        render_buffs("关卡效果", view.buffs)
    elif stage_buffs:
        render_buffs("关卡效果", stage_buffs)

    console.print("[bold cyan]敌人波次[/bold cyan]")
    for wave in view.waves:
        table = Table(title=f"第 {wave.number} 波 · 等级 {wave.level}", header_style="bold")
        table.add_column("敌人", overflow="fold")
        table.add_column("数量", justify="right", overflow="fold")
        wave_phases = max((len(enemy.phase_hps) for enemy in wave.enemies), default=1)
        same_phase_hp = wave_phases > 1 and all(
            len(enemy.phase_hps) == wave_phases
            and len(set(enemy.phase_hps)) == 1
            for enemy in wave.enemies
        )
        if wave_phases > 1 and not same_phase_hp:
            for phase in range(1, wave_phases + 1):
                table.add_column(f"P{phase}", justify="right", overflow="fold")
        else:
            table.add_column("生命值", justify="right", overflow="fold")
        for enemy in wave.enemies:
            cells = [enemy.name, _enemy_count_text(enemy.count)]
            if same_phase_hp:
                cells.append(f"{enemy.phase_hps[0]:,} × {wave_phases}")
            elif wave_phases > 1:
                cells.extend(
                    f"{value:,}" for value in enemy.phase_hps[:wave_phases]
                )
            else:
                cells.append(f"{enemy.hp:,}")
            table.add_row(*cells)
        console.print(table)


def render_maze(
    view: MazeView,
    seen_buffs: set[tuple[str, str]] | None = None,
) -> None:
    """Render both halves of one 混沌 node while keeping shared effects concise."""
    seen = seen_buffs if seen_buffs is not None else set()
    for index, part in enumerate(view.parts):
        if index and not PDF_OUTPUT:
            _print_markdown([""]) if MARKDOWN_OUTPUT else console.print()
        render_highmode(part, stage_buffs=_unique_buffs(part.buffs, seen))


def _diff_table(
    headers: tuple[str, str] = ("项目", "变更"),
    title: str | None = None,
) -> Table:
    table = Table(title=title, header_style="bold cyan")
    table.add_column(headers[0], style="white", overflow="fold")
    table.add_column(headers[1], overflow="fold")
    return table


def _json_change_markup(change: Any) -> str:
    if is_missing(change.before):
        return f"[green]新增：{escape(_terminal_text(format_value(change.after)))}[/green]"
    if is_missing(change.after):
        return f"[red]删除：{escape(_terminal_text(format_value(change.before)))}[/red]"
    return _rich_text_diff_markup(
        _terminal_text(format_value(change.before)),
        _terminal_text(format_value(change.after)),
        arrow=True,
        numeric_only=False,
        convert_multiplication=True,
    )


def _character_change_markup(change: CharacterChange) -> str:
    if change.kind == "added":
        return f"[green]新增：{escape(_terminal_text(change.after or ''))}[/green]"
    if change.kind == "removed":
        return f"[red]删除：{escape(_terminal_text(change.before or ''))}[/red]"
    return _shared_text_markup(change.before or "", change.after or "")


def _lightcone_change_markup(change: LightConeChange) -> str:
    if change.kind == "added":
        return f"[green]新增：{escape(_terminal_text(change.after or ''))}[/green]"
    if change.kind == "removed":
        return f"[red]删除：{escape(_terminal_text(change.before or ''))}[/red]"
    return _lightcone_text_markup(change.before or "", change.after or "")


def _highmode_change_markup(change: HighModeChange, style: str) -> str:
    if change.kind == "added":
        return f"[green]新增：{escape(_terminal_text(change.after or ''))}[/green]"
    if change.kind == "removed":
        return f"[red]删除：{escape(_terminal_text(change.before or ''))}[/red]"
    if style == "hp":
        return _rich_text_diff_markup(
            change.before or "",
            change.after or "",
            arrow=True,
            whole=True,
            convert_multiplication=True,
        )
    return _shared_text_arrow_markup(change.before or "", change.after or "")


def _base_change_markup(change: CharacterChange | LightConeChange) -> str:
    if change.kind == "added":
        return f"[green]新增：{escape(_terminal_text(change.after or ''))}[/green]"
    if change.kind == "removed":
        return f"[red]删除：{escape(_terminal_text(change.before or ''))}[/red]"
    return (
        f"[red strike]{escape(_terminal_text(change.before or ''))}[/red strike] "
        f"[green]{escape(_terminal_text(change.after or ''))}[/green]"
    )


def _highmode_effect_markup(change: HighModeChange) -> str:
    if change.kind == "added":
        return f"[green]{escape(_terminal_text(change.after or ''))}[/green]"
    if change.kind == "removed":
        return f"[red]{escape(_terminal_text(change.before or ''))}[/red]"
    return _rich_text_diff_markup(
        change.before or "",
        change.after or "",
        arrow=False,
        numeric_only=False,
        change_separator=" ",
        convert_multiplication=True,
    )


def _highmode_status_table(
    changes: list[HighModeChange],
    title: str | None = None,
) -> Table:
    table = Table(title=title, show_header=False)
    table.add_column(style="white", overflow="fold")
    table.add_column(no_wrap=True, overflow="fold")
    table.add_column(overflow="fold")
    for change in changes:
        if change.kind == "added":
            color = "green"
            status = "新增"
        elif change.kind == "removed":
            color = "red"
            status = "删除"
        else:
            color = "yellow"
            status = "更改"
        table.add_row(
            Text(highmode_change_subject(change), style=color),
            Text(status, style=color),
            Text.from_markup(_highmode_effect_markup(change)),
        )
    return table


def _base_stat_table(changes: list[CharacterChange]) -> Table:
    table = Table(show_header=False, padding=(0, 2), box=box.SQUARE)
    for change in changes:
        table.add_column(style="white", overflow="fold")
    table.add_row(*(Text(change.label, style="white") for change in changes))
    table.add_row(*(Text.from_markup(_base_change_markup(change)) for change in changes))
    return table


def render_diff(report: DiffReport) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_diff(report)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(_markdown_diff(report))
        return
    changed = report.changed_resources
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", no_wrap=True)
    summary.add_column(overflow="fold")
    summary.add_row("版本", f"{report.version_one} → {report.version_two}")
    summary.add_row("模式", _mode_label(report.mode))
    summary.add_row("变更资源数", str(len(changed)))
    summary.add_row("已变更", str(len(changed)))
    console.print(Panel(summary, title="数据差异", border_style="cyan"))

    if not changed:
        console.print("[dim]未发现变更。[/dim]")
        return

    table = Table(header_style="bold cyan")
    table.add_column("资源", overflow="fold")
    table.add_column("状态", overflow="fold")
    table.add_column("变更数", justify="right", overflow="fold")
    for resource in changed:
        table.add_row(
            resource.resource_id,
            STATUS_LABELS.get(resource.status, resource.status),
            str(resource.change_count),
        )
    if changed:
        console.print(table)

    for resource in changed:
        console.print(
            f"[bold cyan]{_mode_label(report.mode)}/{resource.resource_id}.json[/bold cyan] "
            f"[dim]（{resource.change_count} 项变更）[/dim]"
        )
        table = _diff_table(("路径", "变更"))
        for change in resource.changes:
            table.add_row(
                Text(change.path, style="white"),
                Text.from_markup(_json_change_markup(change)),
            )
        console.print(table)
        if resource.change_count > len(resource.changes):
            console.print(
                f"[dim]仅显示前 {len(resource.changes)} 项变更。[/dim]"
            )


def render_character_diff(
    report: CharacterDiffReport,
    verbose: bool = False,
) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_character_diff(report, verbose)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(_markdown_character_diff(report, verbose))
        return
    sections = tuple(
        section
        for section in report.sections
        if verbose or section.name != "特殊效果"
    )
    changed_sections = tuple(section for section in sections if section.status != "unchanged")
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", no_wrap=True)
    summary.add_column(overflow="fold")
    summary.add_row("版本", f"{report.version_one} → {report.version_two}")
    summary.add_row("角色", format_name_change(report.name_one, report.name_two))
    summary.add_row("变更分类数", str(len(changed_sections)))
    summary.add_row("已变更", str(len(changed_sections)))
    console.print(Panel(summary, title="角色差异", border_style="cyan"))

    if not changed_sections:
        console.print("[dim]未发现变更。[/dim]")
        return

    table = Table(header_style="bold cyan")
    table.add_column("分类", overflow="fold")
    table.add_column("状态", overflow="fold")
    table.add_column("变更数", justify="right", overflow="fold")
    for section in changed_sections:
        status = {"changed": "已变更", "unchanged": "未变更"}.get(
            section.status,
            section.status,
        )
        table.add_row(section.name, status, str(len(section.changes)))
    if changed_sections:
        console.print(table)

    for section in changed_sections:
        console.print(f"[bold cyan]{section.name}[/bold cyan]")
        changes = sorted(section.changes, key=_character_change_sort_key)
        if section.name == "基础属性":
            console.print(_base_stat_table(changes))
            continue
        table = _diff_table()
        for change in changes:
            table.add_row(
                Text(character_change_subject(section.name, change), style="white"),
                Text.from_markup(_character_change_markup(change)),
            )
        console.print(table)


def render_lightcone_diff(report: LightConeDiffReport) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_lightcone_diff(report)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(_markdown_lightcone_diff(report))
        return
    sections = report.sections
    changed_sections = tuple(section for section in sections if section.status != "unchanged")
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan", no_wrap=True)
    summary.add_column(overflow="fold")
    summary.add_row("版本", f"{report.version_one} → {report.version_two}")
    summary.add_row("光锥", format_name_change(report.name_one, report.name_two))
    summary.add_row("变更分类数", str(len(changed_sections)))
    summary.add_row("已变更", str(len(changed_sections)))
    console.print(Panel(summary, title="光锥差异", border_style="cyan"))

    if not changed_sections:
        console.print("[dim]未发现变更。[/dim]")
        return

    table = Table(header_style="bold cyan")
    table.add_column("分类", overflow="fold")
    table.add_column("状态", overflow="fold")
    table.add_column("变更数", justify="right", overflow="fold")
    for section in changed_sections:
        status = {"changed": "已变更", "unchanged": "未变更"}.get(
            section.status,
            section.status,
        )
        table.add_row(section.name, status, str(len(section.changes)))
    if changed_sections:
        console.print(table)

    for section in changed_sections:
        console.print(f"[bold cyan]{section.name}[/bold cyan]")
        changes = sorted(section.changes, key=_lightcone_change_sort_key)
        if section.name == "基础属性":
            for change in changes:
                _render_base_stat_change(change)
            continue
        table = _diff_table()
        for change in changes:
            table.add_row(
                Text(change.label, style="white"),
                Text.from_markup(_lightcone_change_markup(change)),
            )
        console.print(table)


def _render_lightcone_change(change: LightConeChange) -> None:
    if change.kind == "added":
        body = f"[green]新增：{escape(change.after or '')}[/green]"
        border_style = "magenta"
    elif change.kind == "removed":
        body = f"[red]删除：{escape(change.before or '')}[/red]"
        border_style = "magenta"
    else:
        body = _lightcone_text_markup(change.before or "", change.after or "")
        border_style = "magenta"
    console.print(
        Panel(
            body,
            title=escape(change.label),
            border_style=border_style,
        )
    )


def _render_base_stat_change(
    change: CharacterChange | LightConeChange,
) -> None:
    label = escape(change.label)
    if change.kind == "added":
        console.print(f"[bold]{label}[/bold]：[green]新增：{escape(change.after or '')}[/green]")
    elif change.kind == "removed":
        console.print(f"[bold]{label}[/bold]：[red]删除：{escape(change.before or '')}[/red]")
    else:
        console.print(
            f"[bold]{label}[/bold]："
            f"[red strike]{escape(change.before or '')}[/red strike] "
            f"[green]{escape(change.after or '')}[/green]"
        )


def _lightcone_change_sort_key(change: LightConeChange) -> tuple[int, str]:
    priority = {"removed": 0, "added": 1, "changed": 2}
    return priority.get(change.kind, 3), change.label


def _render_character_change(change: CharacterChange) -> None:
    if change.kind == "added":
        body = f"[green]新增：{escape(change.after or '')}[/green]"
        border_style = "magenta"
    elif change.kind == "removed":
        body = f"[red]删除：{escape(change.before or '')}[/red]"
        border_style = "magenta"
    else:
        body = _shared_text_markup(change.before or "", change.after or "")
        border_style = "magenta"
    console.print(
        Panel(
            body,
            title=escape(change.label),
            border_style=border_style,
        )
    )


def _character_change_sort_key(change: CharacterChange) -> tuple[int, str]:
    priority = {"removed": 0, "added": 1, "changed": 2}
    return priority.get(change.kind, 3), change.label


def _rich_text_diff_markup(
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
    if convert_multiplication:
        old_value = _terminal_text(old_value)
        new_value = _terminal_text(new_value)
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


def _shared_text_markup(old_value: str, new_value: str) -> str:
    return _rich_text_diff_markup(
        old_value,
        new_value,
        arrow=False,
        convert_multiplication=True,
    )


def _shared_text_arrow_markup(old_value: str, new_value: str) -> str:
    return _rich_text_diff_markup(
        old_value,
        new_value,
        arrow=True,
        convert_multiplication=True,
    )


def _lightcone_text_markup(old_value: str, new_value: str) -> str:
    return _rich_text_diff_markup(
        old_value,
        new_value,
        arrow=False,
        refinement=True,
        convert_multiplication=True,
    )


def _markdown_shared_text_markup(old_value: str, new_value: str) -> str:
    return _rich_text_diff_markup(old_value, new_value, arrow=False)


def _markdown_shared_text_arrow_markup(old_value: str, new_value: str) -> str:
    return _rich_text_diff_markup(old_value, new_value, arrow=True)


def _markdown_lightcone_text_markup(old_value: str, new_value: str) -> str:
    return _rich_text_diff_markup(
        old_value,
        new_value,
        arrow=False,
        refinement=True,
    )


def render_highmode_diff(report: HighModeDiffReport, include_header: bool = True) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_highmode_diff(report)
        return
    if MARKDOWN_OUTPUT:
        _print_markdown(_markdown_highmode_diff(report, include_header))
        return
    changed_sections = report.changed_sections
    if not changed_sections:
        console.print("[dim]未发现变更。[/dim]")
        return

    if include_header:
        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="bold cyan", no_wrap=True)
        summary.add_column(overflow="fold")
        summary.add_row("版本", f"{report.version_one} → {report.version_two}")
        summary.add_row("模式", _mode_label(report.mode))
        console.print(Panel(summary, title=f"{_mode_label(report.mode)}差异", border_style="cyan"))
    for section in changed_sections:
        console.print(f"[bold cyan]{_highmode_section_label(section.name)}[/bold cyan]")
        effect_changes = tuple(change for change in section.changes if change.category == "effects")
        if effect_changes:
            console.print("[bold cyan]关卡效果[/bold cyan]")
            console.print(_highmode_status_table(
                sorted(effect_changes, key=_highmode_change_sort_key),
            ))

        hp_changes = tuple(change for change in section.changes if change.category == "hp")
        if hp_changes:
            waves: dict[int, list] = {}
            for change in hp_changes:
                wave = highmode_change_wave(change) or 0
                waves.setdefault(wave, []).append(change)
            for wave, changes in waves.items():
                wave_label = "首领" if wave == 0 else f"第 {wave} 波"
                table = _highmode_status_table(
                    sorted(changes, key=_highmode_change_sort_key),
                    wave_label,
                )
                console.print(table)

        metadata_changes = tuple(
            change for change in section.changes if change.category == "metadata"
        )
        if metadata_changes:
            console.print("[bold cyan]基本信息[/bold cyan]")
            table = _diff_table(("项目", "变更"))
            for change in sorted(metadata_changes, key=_highmode_change_sort_key):
                table.add_row(
                    Text(_highmode_metadata_label(change.label), style="white"),
                    Text.from_markup(_highmode_change_markup(change, "highmode")),
                )
            console.print(table)


def _highmode_change_sort_key(change: HighModeChange) -> tuple[int, str]:
    priority = {"removed": 0, "added": 1, "changed": 2}
    return priority.get(change.kind, 3), change.label


def _choice_table(
    title: str,
    options: tuple[tuple[str, str], ...],
    *,
    all_label: str | None = None,
) -> Table:
    table = Table(title=title, header_style="bold cyan")
    table.add_column("编号", justify="right", style="bold yellow", no_wrap=True, overflow="fold")
    table.add_column("选项", style="bold", overflow="fold")
    table.add_column("说明", overflow="fold")
    if all_label is not None:
        table.add_row("0", all_label, "选择全部")
    for index, (value, label) in enumerate(options, start=1):
        table.add_row(str(index), label, value)
    return table


def _prompt_index(
    title: str,
    options: tuple[tuple[str, str], ...],
    *,
    all_label: str | None = None,
) -> int | None:
    if not options:
        console.print("[yellow]没有可选择的项目。[/yellow]")
        return None
    console.print(_choice_table(title, options, all_label=all_label))
    choices = [str(index) for index in range(1, len(options) + 1)]
    if all_label is not None:
        choices.insert(0, "0")
    answer = Prompt.ask(
        title,
        choices=[*choices, "q"],
        default="q",
    )
    if answer == "q":
        return None
    return int(answer)


def _prompt_record(
    catalog: tuple[VersionRecord, ...],
    title: str = "选择版本组",
) -> VersionRecord | None:
    options = tuple(
        (
            record.name,
            f"版本组 {record.name}（{len(record.versions)} 个版本）",
        )
        for record in catalog
    )
    index = _prompt_index(title, options)
    return catalog[index - 1] if index is not None else None


def _prompt_release(
    record: VersionRecord,
    title: str,
    *,
    excluded: frozenset[str] = frozenset(),
) -> str | None:
    versions = tuple(version for version in record.versions if version not in excluded)
    options = tuple((version, "可比较版本") for version in versions)
    index = _prompt_index(title, options)
    return versions[index - 1] if index is not None else None


def _pause_interactive_result() -> None:
    Prompt.ask("按回车返回主菜单", default="")


def _query_mode_options() -> tuple[tuple[str, str], ...]:
    return (
        ("character", "角色"),
        ("lightcone", "光锥"),
        ("maze", "混沌"),
        ("story", "虚构"),
        ("boss", "末日"),
        ("peak", "异相（全部）"),
        ("knight", "骑士"),
        ("king", "王棋"),
        ("hard-king", "绝境"),
    )


def _query_resource_mode(mode: str) -> str:
    return "peak" if mode in {"peak", "knight", "king", "hard-king"} else mode


def _prompt_full_resource_id(full_catalog: FullCatalog, mode: str) -> int | None:
    label = _mode_label(mode)
    ids = full_catalog.resource_ids(mode)
    if not ids:
        console.print(f"[yellow]完整数据目录中没有{label}资源。[/yellow]")
        return None
    while True:
        answer = Prompt.ask(
            f"输入{label}数据 ID（{ids[0]} 至 {ids[-1]}，输入 q 返回）",
            default="q",
        )
        if answer.lower() == "q":
            return None
        if answer.isdigit() and full_catalog.contains(mode, answer):
            return int(answer)
        console.print(f"[red]{label}数据 ID {answer!r} 不在 full.json 中。[/red]")


def _show_mode_options(record: VersionRecord) -> tuple[tuple[str, str], ...]:
    options: list[tuple[str, str]] = []
    if record.character:
        options.append(("character", "角色"))
    if record.lightcone:
        options.append(("lightcone", "光锥"))
    if record.maze:
        options.append(("maze", "混沌"))
    if record.story:
        options.append(("story", "虚构"))
    if record.boss:
        options.append(("boss", "末日"))
    if record.peak:
        options.extend(
            (
                ("peak", "异相（全部）"),
                ("knight", "骑士"),
                ("king", "王棋"),
                ("hard-king", "绝境"),
            )
        )
    return tuple(options)


def _diff_mode_options(
    record_one: VersionRecord,
    record_two: VersionRecord,
) -> tuple[tuple[str, str], ...]:
    options: list[tuple[str, str]] = []
    for mode, label in (
        ("character", "角色"),
        ("lightcone", "光锥"),
        ("maze", "混沌"),
        ("story", "虚构"),
        ("boss", "末日"),
        ("peak", "异相（全部）"),
        ("knight", "骑士"),
        ("king", "王棋"),
        ("hard-king", "绝境"),
    ):
        resource_mode = "peak" if mode in {"knight", "king", "hard-king"} else mode
        first = getattr(record_one, resource_mode)
        second = getattr(record_two, resource_mode)
        if first and second:
            options.append((mode, label))
    return tuple(options)


def _run_show_wizard(
    catalog: tuple[VersionRecord, ...],
    version_or_mode: str | None = None,
    mode_or_node: str | None = None,
    node: int | None = None,
    verbose: bool = False,
) -> None:
    preset_node = node
    if version_or_mode == "knight":
        record = max(catalog, key=lambda item: max(item.versions, default=""))
        version = max(record.versions)
        preset_mode = "knight"
        if mode_or_node is not None:
            preset_node = int(mode_or_node)
    else:
        record = None
        version = version_or_mode
        preset_mode = mode_or_node.lower() if mode_or_node else None

    if record is None:
        if version is None:
            record = _prompt_record(catalog)
            if record is None:
                return
            version = _prompt_release(record, "选择版本")
            if version is None:
                return
        else:
            try:
                record = find_release(catalog, version)
            except KeyError:
                console.print(f"[red]未找到版本 {version}。[/red]")
                return

    if preset_mode is None:
        mode_index = _prompt_index("选择查看模式", _show_mode_options(record))
        if mode_index is None:
            return
        preset_mode = _show_mode_options(record)[mode_index - 1][0]
    if preset_mode not in {value for value, _ in _show_mode_options(record)}:
        console.print(f"[red]版本 {version} 不支持模式 {preset_mode}。[/red]")
        return

    if preset_mode == "character":
        if preset_node is None:
            index = _prompt_index(
                "选择角色",
                tuple((resource_id, f"角色 {index}") for index, resource_id in enumerate(record.character, 1)),
            )
            if index is None:
                return
            preset_node = index
        if not verbose:
            verbose_index = _prompt_index(
                "是否显示特殊效果",
                (("no", "不显示"), ("yes", "显示")),
            )
            if verbose_index is None:
                return
            verbose = verbose_index == 2
    elif preset_mode == "lightcone":
        if preset_node is None:
            index = _prompt_index(
                "选择光锥",
                tuple((resource_id, f"光锥 {index}") for index, resource_id in enumerate(record.lightcone, 1)),
            )
            if index is None:
                return
            preset_node = index
    elif preset_mode == "boss":
        nodes = available_boss_nodes(version, record.boss)
        if preset_node is None:
            index = _prompt_index(
                "选择末日节点",
                tuple((str(item), f"节点 {item}") for item in nodes),
                all_label="全部节点",
            )
            if index is None:
                return
            preset_node = None if index == 0 else index
    elif preset_mode == "story":
        nodes = available_story_nodes(version, record.story)
        if preset_node is None:
            index = _prompt_index(
                "选择虚构节点",
                tuple((str(item), f"节点 {item}") for item in nodes),
                all_label="全部节点",
            )
            if index is None:
                return
            preset_node = None if index == 0 else index
    elif preset_mode == "maze":
        nodes = available_maze_nodes(version, record.maze)
        if preset_node is None:
            index = _prompt_index(
                "选择混沌节点",
                tuple((str(item), f"节点 {item}") for item in nodes),
                all_label="全部节点",
            )
            if index is None:
                return
            preset_node = None if index == 0 else index
    elif preset_mode == "knight":
        if preset_node is None:
            index = _prompt_index(
                "选择骑士",
                tuple((str(item), f"骑士 {item}") for item in (1, 2, 3)),
                all_label="全部骑士",
            )
            if index is None:
                return
            preset_node = None if index == 0 else index
    else:
        preset_node = None

    show(version, preset_mode, preset_node, verbose)
    _pause_interactive_result()


def _run_diff_wizard(
    catalog: tuple[VersionRecord, ...],
    version_one: str | None = None,
    version_two: str | None = None,
    mode: str | None = None,
    node: int | None = None,
    verbose: bool = False,
) -> None:
    record: VersionRecord | None = None
    if version_one is not None:
        try:
            record = find_release(catalog, version_one)
        except KeyError:
            console.print(f"[red]未找到版本 {version_one}。[/red]")
            return
    elif version_two is not None:
        try:
            record = find_release(catalog, version_two)
        except KeyError:
            console.print(f"[red]未找到版本 {version_two}。[/red]")
            return
    else:
        record = _prompt_record(catalog)
        if record is None:
            return

    if version_one is None:
        version_one = _prompt_release(
            record,
            "选择旧版本",
            excluded=frozenset({version_two}) if version_two else frozenset(),
        )
        if version_one is None:
            return
    if version_two is None:
        version_two = _prompt_release(
            record,
            "选择新版本",
            excluded=frozenset({version_one}),
        )
        if version_two is None:
            return

    record_two = find_release(catalog, version_two)
    if record.name != record_two.name:
        console.print("[red]两个版本必须属于同一版本组。[/red]")
        return

    if mode is None:
        mode_index = _prompt_index(
            "选择比较模式",
            _diff_mode_options(record, record_two),
        )
        if mode_index is None:
            return
        mode = _diff_mode_options(record, record_two)[mode_index - 1][0]
    mode = mode.lower()

    if mode in {"character", "lightcone"} and node is None:
        resources = getattr(record, mode)
        resource_name = "角色" if mode == "character" else "光锥"
        index = _prompt_index(
            f"选择{resource_name}",
            tuple((resource_id, f"{resource_name} {index}") for index, resource_id in enumerate(resources, 1)),
            all_label=f"全部{resource_name}",
        )
        if index is None:
            return
        node = None if index == 0 else index
        if mode == "character" and not verbose:
            verbose_index = _prompt_index(
                "是否显示特殊效果差异",
                (("no", "不显示"), ("yes", "显示")),
            )
            if verbose_index is None:
                return
            verbose = verbose_index == 2
    elif mode == "story" and node is None:
        nodes = available_story_nodes(version_one, record.story)
        index = _prompt_index(
            "选择虚构节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "maze" and node is None:
        nodes = available_maze_nodes(version_one, record.maze)
        index = _prompt_index(
            "选择混沌节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "knight" and node is None:
        index = _prompt_index(
            "选择骑士",
            tuple((str(item), f"骑士 {item}") for item in (1, 2, 3)),
            all_label="全部骑士",
        )
        if index is None:
            return
        node = None if index == 0 else index

    diff(version_one, version_two, mode, node, verbose)
    _pause_interactive_result()


def _run_query_wizard(
    catalog: tuple[VersionRecord, ...],
    mode: str | None = None,
    resource_id: int | None = None,
    node: int | None = None,
    verbose: bool = False,
) -> None:
    if mode is None:
        mode_index = _prompt_index("选择查询模式", _query_mode_options())
        if mode_index is None:
            return
        mode = _query_mode_options()[mode_index - 1][0]
    mode = mode.lower()
    if mode not in {value for value, _ in _query_mode_options()}:
        console.print(f"[red]不支持的查询模式 {mode}。[/red]")
        return

    full_catalog = _load_full_data()
    resource_mode = _query_resource_mode(mode)
    if resource_id is None:
        resource_id = _prompt_full_resource_id(full_catalog, resource_mode)
        if resource_id is None:
            return

    version = latest_release(catalog)
    console.print(f"[dim]使用最新版本 {version}。[/dim]")

    if mode == "character" and not verbose:
        verbose_index = _prompt_index(
            "是否显示特殊效果",
            (("no", "不显示"), ("yes", "显示")),
        )
        if verbose_index is None:
            return
        verbose = verbose_index == 2
    elif mode == "boss" and node is None:
        nodes = available_boss_nodes(version, str(resource_id))
        index = _prompt_index(
            "选择末日节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "story" and node is None:
        nodes = available_story_nodes(version, str(resource_id))
        index = _prompt_index(
            "选择虚构节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "maze" and node is None:
        nodes = available_maze_nodes(version, str(resource_id))
        index = _prompt_index(
            "选择混沌节点",
            tuple((str(item), f"节点 {item}") for item in nodes),
            all_label="全部节点",
        )
        if index is None:
            return
        node = None if index == 0 else index
    elif mode == "knight" and node is None:
        index = _prompt_index(
            "选择骑士",
            tuple((str(item), f"骑士 {item}") for item in (1, 2, 3)),
            all_label="全部骑士",
        )
        if index is None:
            return
        node = None if index == 0 else index

    query(mode, resource_id, node, verbose=verbose)
    _pause_interactive_result()


def _run_catalog_browser(catalog: tuple[VersionRecord, ...]) -> None:
    while True:
        console.clear()
        index = _prompt_index(
            "浏览版本信息",
            tuple(
                (record.name, f"版本组 {record.name}")
                for record in catalog
            ),
        )
        if index is None:
            return
        console.print(detail_panel(catalog[index - 1]))
        action = Prompt.ask("按回车继续浏览，输入 q 返回主菜单", default="")
        if action.lower() == "q":
            return


def _run_tui(catalog: tuple[VersionRecord, ...]) -> None:
    if not catalog:
        console.print("[yellow]版本目录为空。[/yellow]")
        return

    if not sys.stdin.isatty():
        render_catalog(catalog)
        return

    while True:
        console.clear()
        render_catalog(catalog)
        choice = _prompt_index(
            "选择操作",
            (
                ("show", "查看数据"),
                ("diff", "比较版本差异"),
                ("query", "全量数据查询"),
                ("catalog", "浏览版本信息"),
            ),
        )
        if choice is None:
            return
        if choice == 1:
            _run_show_wizard(catalog)
        elif choice == 2:
            _run_diff_wizard(catalog)
        elif choice == 3:
            _run_query_wizard(catalog)
        else:
            _run_catalog_browser(catalog)


def run_tui(catalog: tuple[VersionRecord, ...]) -> None:
    with _terminal_output():
        _run_tui(catalog)


def _load_data() -> tuple[VersionRecord, ...]:
    try:
        return load_catalog()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        _abort_cli(error)


def _load_full_data() -> FullCatalog:
    try:
        return load_full_catalog()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        _abort_cli(error)


def _batch_separator(has_output: bool) -> None:
    if not has_output or PDF_OUTPUT:
        return
    if MARKDOWN_OUTPUT:
        _print_markdown([""])
    else:
        console.print()


def _begin_pdf_mode(title: str) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.begin_mode(title)


def _begin_pdf_diff_mode(title: str) -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.begin_diff_mode(title)


def _render_show_all(
    version: str,
    record: VersionRecord,
    verbose: bool,
) -> None:
    """Render every configured mode in the stable export order."""
    has_output = False

    def emit(title: str, render: Callable[[], None]) -> None:
        nonlocal has_output
        _batch_separator(has_output)
        try:
            render()
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            render_batch_error(title, error)
        has_output = True

    def emit_error(title: str, error: Exception) -> None:
        nonlocal has_output
        _batch_separator(has_output)
        render_batch_error(title, error)
        has_output = True

    for index, resource_id in enumerate(record.character):
        if index == 0:
            _begin_pdf_mode("角色")
        emit(
            f"角色 · {resource_id}",
            lambda resource_id=resource_id: render_character(
                load_character(version, resource_id), verbose
            ),
        )
    for index, resource_id in enumerate(record.lightcone):
        if index == 0:
            _begin_pdf_mode("光锥")
        emit(
            f"光锥 · {resource_id}",
            lambda resource_id=resource_id: render_lightcone(
                load_lightcone(version, resource_id)
            ),
        )

    if record.maze:
        try:
            maze_nodes = available_maze_nodes(version, record.maze)
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            _begin_pdf_mode("混沌")
            emit_error("混沌", error)
        else:
            if maze_nodes:
                _begin_pdf_mode("混沌")
            seen_maze_buffs: set[tuple[str, str]] = set()
            for maze_node in maze_nodes:
                emit(
                    f"混沌 · 节点 {maze_node}",
                    lambda maze_node=maze_node: render_maze(
                        load_maze(version, record.maze, maze_node),
                        seen_maze_buffs,
                    ),
                )

    if record.story:
        try:
            story_nodes = available_story_nodes(version, record.story)
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            _begin_pdf_mode("虚构")
            emit_error("虚构", error)
        else:
            if story_nodes:
                _begin_pdf_mode("虚构")
            def render_story_node(node: int, first: bool) -> None:
                view = load_story(version, record.story, node)
                render_highmode(
                    view,
                    prelude_buffs=view.season_buffs if first else (),
                )

            for index, node in enumerate(story_nodes):
                emit(
                    f"虚构 · 节点 {node}",
                    lambda node=node, index=index: render_story_node(node, index == 0),
                )

    if record.boss:
        try:
            boss_nodes = available_boss_nodes(version, record.boss)
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            _begin_pdf_mode("末日")
            emit_error("末日", error)
        else:
            if boss_nodes:
                _begin_pdf_mode("末日")
            for node in boss_nodes:
                emit(
                    f"末日 · 节点 {node}",
                    lambda node=node: render_boss(
                        load_boss(version, record.boss, node)
                    ),
                )

    if record.peak:
        _begin_pdf_mode("异相")
        for mode, node in BATCH_PEAK_SECTIONS:
            title = _mode_label(mode) if node is None else f"{_mode_label(mode)} {node}"
            emit(
                title,
                lambda mode=mode, node=node: render_highmode(
                    load_peak(version, record.peak, mode, node)
                ),
            )


def _render_diff_all(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    verbose: bool,
) -> bool:
    """Render changed resources in the same order used by batch show."""
    has_output = False

    def emit(render: Callable[[], None]) -> None:
        nonlocal has_output
        _batch_separator(has_output)
        render()
        has_output = True

    if record_one.character and record_two.character:
        all_reports = compare_all_character_versions(
            version_one, version_two, record_one, record_two
        )
        if PDF_OUTPUT and PDF_RENDERER is not None:
            for report in all_reports:
                PDF_RENDERER.register_diff_overview(report, verbose)
        reports = tuple(
            report
            for report in all_reports
            if any(
                section.status != "unchanged"
                and (verbose or section.name != "特殊效果")
                for section in report.sections
            )
        )
        if reports:
            _begin_pdf_diff_mode("角色差异")
        for report in reports:
            emit(lambda report=report: render_character_diff(report, verbose))

    if record_one.lightcone and record_two.lightcone:
        all_reports = compare_all_lightcone_versions(
            version_one, version_two, record_one, record_two
        )
        if PDF_OUTPUT and PDF_RENDERER is not None:
            for report in all_reports:
                PDF_RENDERER.register_diff_overview(report)
        reports = tuple(
            report for report in all_reports if report.changed_sections
        )
        if reports:
            _begin_pdf_diff_mode("光锥差异")
        for report in reports:
            emit(lambda report=report: render_lightcone_diff(report))

    if record_one.maze and record_two.maze:
        all_reports = compare_all_maze_versions(
            version_one, version_two, record_one, record_two
        )
        if PDF_OUTPUT and PDF_RENDERER is not None:
            for report in all_reports:
                PDF_RENDERER.register_diff_overview(report)
        reports = tuple(
            report for report in all_reports if report.changed_sections
        )
        if reports:
            _begin_pdf_diff_mode("混沌差异")
        for index, report in enumerate(reports):
            emit(lambda report=report, index=index: render_highmode_diff(report, index == 0))

    if record_one.story and record_two.story:
        all_reports = compare_all_story_versions(
            version_one, version_two, record_one, record_two
        )
        if PDF_OUTPUT and PDF_RENDERER is not None:
            for report in all_reports:
                PDF_RENDERER.register_diff_overview(report)
        reports = tuple(
            report for report in all_reports if report.changed_sections
        )
        if reports:
            _begin_pdf_diff_mode("虚构差异")
        for index, report in enumerate(reports):
            emit(lambda report=report, index=index: render_highmode_diff(report, index == 0))

    if record_one.boss and record_two.boss:
        all_reports = compare_all_boss_versions(
            version_one, version_two, record_one, record_two
        )
        if PDF_OUTPUT and PDF_RENDERER is not None:
            for report in all_reports:
                PDF_RENDERER.register_diff_overview(report)
        reports = tuple(
            report for report in all_reports if report.changed_sections
        )
        if reports:
            _begin_pdf_diff_mode("末日差异")
        for index, report in enumerate(reports):
            emit(lambda report=report, index=index: render_highmode_diff(report, index == 0))

    if record_one.peak and record_two.peak:
        report = compare_highmode_versions(
            version_one,
            version_two,
            "peak",
            None,
            record_one,
            record_two,
        )
        if PDF_OUTPUT and PDF_RENDERER is not None:
            PDF_RENDERER.register_diff_overview(report)
        if report.changed_sections:
            _begin_pdf_diff_mode("异相差异")
            emit(lambda: render_highmode_diff(report))

    return has_output


@app.callback(invoke_without_command=True)
def main(context: typer.Context) -> None:
    """未指定命令时启动交互式导航菜单。"""
    if context.invoked_subcommand is None:
        run_tui(_load_data())


@app.command("list")
def list_versions(
    markdown: bool = typer.Option(False, "--markdown", help="以 Markdown 格式输出。"),
    pdf: bool = typer.Option(False, "--pdf", help="以 PDF 格式输出到标准输出。请使用 > 保存文件。"),
) -> None:
    """打印目录中的所有版本组。"""
    if markdown and pdf:
        _abort_cli("--markdown 和 --pdf 不能同时使用。")
    if pdf and sys.stdout.isatty():
        _abort_cli("--pdf 输出的是二进制数据，请使用 hvi list --pdf > versions.pdf。")
    global MARKDOWN_OUTPUT, PDF_OUTPUT, PDF_RENDERER
    previous_markdown = MARKDOWN_OUTPUT
    previous_pdf = PDF_OUTPUT
    previous_renderer = PDF_RENDERER
    MARKDOWN_OUTPUT = markdown
    PDF_OUTPUT = pdf
    PDF_RENDERER = PdfRenderer() if pdf else None
    try:
        render_catalog(_load_data())
        if pdf:
            _write_pdf()
    finally:
        MARKDOWN_OUTPUT = previous_markdown
        PDF_OUTPUT = previous_pdf
        PDF_RENDERER = previous_renderer


@app.command("download")
def download_command() -> None:
    """同步最新版本全量数据和历史版本所需数据。"""
    download_all(_load_data(), _load_full_data())


@app.command("cleanup")
def cleanup_command() -> None:
    """删除历史版本中不再被 show 或 diff 使用的全量缓存。"""
    removed = cleanup_data(_load_data(), _load_full_data())
    if removed:
        console.print(f"已清理 {len(removed)} 个历史版本的冗余数据文件。")
    else:
        console.print("[dim]没有可清理的历史版本冗余数据。[/dim]")


def _render_query(
    version: str,
    mode: str,
    resource_id: int,
    node: int | None,
    verbose: bool,
) -> None:
    resource = str(resource_id)
    if mode == "character":
        if node is not None:
            raise ValueError("角色查询不接受节点参数。")
        render_character(load_character(version, resource), verbose)
        return
    if mode == "lightcone":
        if node is not None:
            raise ValueError("光锥查询不接受节点参数。")
        render_lightcone(load_lightcone(version, resource))
        return
    if mode == "maze":
        nodes = (node,) if node is not None else available_maze_nodes(version, resource)
        if not nodes:
            raise ValueError(f"混沌数据 {resource} 中未找到节点。")
        seen_buffs: set[tuple[str, str]] = set()
        for index, maze_node in enumerate(nodes):
            if index and not PDF_OUTPUT:
                _print_markdown([""]) if MARKDOWN_OUTPUT else console.print()
            render_maze(load_maze(version, resource, maze_node), seen_buffs)
        return
    if mode == "boss":
        nodes = (node,) if node is not None else available_boss_nodes(version, resource)
        if not nodes:
            raise ValueError(f"末日数据 {resource} 中未找到节点。")
        for index, boss_node in enumerate(nodes):
            if index and not PDF_OUTPUT:
                _print_markdown([""]) if MARKDOWN_OUTPUT else console.print()
            render_boss(load_boss(version, resource, boss_node))
        return
    if mode == "story":
        nodes = (node,) if node is not None else available_story_nodes(version, resource)
        if not nodes:
            raise ValueError(f"虚构数据 {resource} 中未找到节点。")
        for index, story_node in enumerate(nodes):
            if index and not PDF_OUTPUT:
                _print_markdown([""]) if MARKDOWN_OUTPUT else console.print()
            view = load_story(version, resource, story_node)
            render_highmode(
                view,
                prelude_buffs=view.season_buffs if index == 0 else (),
            )
        return
    if mode == "knight":
        nodes = (node,) if node is not None else (1, 2, 3)
        for index, knight_node in enumerate(nodes):
            if knight_node not in (1, 2, 3):
                raise ValueError("骑士节点必须是 1、2 或 3。")
            if index and not PDF_OUTPUT:
                _print_markdown([""]) if MARKDOWN_OUTPUT else console.print()
            render_highmode(load_peak(version, resource, "knight", knight_node))
        return
    if mode in {"king", "hard-king"}:
        if node is not None:
            raise ValueError(f"{_mode_label(mode)}查询不接受节点参数。")
        render_highmode(load_peak(version, resource, mode, None))
        return
    if mode == "peak":
        if node is None:
            sections = (
                ("knight", 1),
                ("knight", 2),
                ("knight", 3),
                ("king", None),
                ("hard-king", None),
            )
        else:
            if node > 5:
                raise ValueError("异相节点必须是 1 到 5。")
            peak_mode = "knight" if node <= 3 else "king" if node == 4 else "hard-king"
            sections = ((peak_mode, node if peak_mode == "knight" else None),)
        for index, (peak_mode, peak_node) in enumerate(sections):
            if index and not PDF_OUTPUT:
                _print_markdown([""]) if MARKDOWN_OUTPUT else console.print()
            render_highmode(load_peak(version, resource, peak_mode, peak_node))
        return
    raise ValueError("支持的查询模式：角色、光锥、混沌、虚构、末日、异相、骑士、王棋和绝境。")


@app.command()
def query(
    mode: str | None = typer.Argument(None, metavar="模式", help="查询模式。"),
    resource_id: int | None = typer.Argument(
        None,
        metavar="数据ID",
        min=1,
        help="full.json 中的角色、光锥或关卡资源 ID。",
    ),
    node: int | None = typer.Argument(
        None,
        metavar="节点",
        min=1,
        help="关卡节点编号；省略时显示该资源的全部节点。",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示角色特殊效果。"),
    markdown: bool = typer.Option(False, "--markdown", help="以 Markdown 格式输出。"),
    pdf: bool = typer.Option(False, "--pdf", help="以 PDF 格式输出到标准输出，请使用 > 保存文件。"),
) -> None:
    """按 full.json 中的真实数据 ID 查询最新版本资源。"""
    global MARKDOWN_OUTPUT, PDF_OUTPUT, PDF_RENDERER
    catalog = _load_data()
    if mode is None or resource_id is None:
        if not sys.stdin.isatty():
            _abort_cli("query 缺少参数；请提供模式和数据 ID。")
        if markdown or pdf:
            option = "--markdown" if markdown else "--pdf"
            _abort_cli(f"{option} 不能用于交互式向导，请补全 query 参数。")
        try:
            with _terminal_output():
                _run_query_wizard(catalog, mode, resource_id, node, verbose)
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            _abort_cli(error)
        return
    if markdown and pdf:
        _abort_cli("--markdown 和 --pdf 不能同时使用。")
    if pdf and sys.stdout.isatty():
        _abort_cli("--pdf 输出的是二进制数据，请使用 hvi query ... --pdf > query.pdf。")

    previous_markdown = MARKDOWN_OUTPUT
    previous_pdf = PDF_OUTPUT
    previous_renderer = PDF_RENDERER
    MARKDOWN_OUTPUT = markdown
    PDF_OUTPUT = pdf
    PDF_RENDERER = PdfRenderer() if pdf else None
    try:
        mode = mode.lower()
        resource_mode = _query_resource_mode(mode)
        full_catalog = _load_full_data()
        if mode not in {value for value, _ in _query_mode_options()}:
            raise ValueError(f"不支持的查询模式 {mode!r}。")
        if not full_catalog.contains(resource_mode, resource_id):
            raise ValueError(
                f"{_mode_label(resource_mode)}数据 ID {resource_id} 不在 full.json 中。"
            )
        version = latest_release(catalog)
        _render_query(version, mode, resource_id, node, verbose)
        if pdf:
            _write_pdf()
    except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
        _abort_cli(f"{error} 请先运行 hvi download。")
    finally:
        MARKDOWN_OUTPUT = previous_markdown
        PDF_OUTPUT = previous_pdf
        PDF_RENDERER = previous_renderer


@app.command()
def diff(
    version_one: str | None = typer.Argument(None, metavar="版本1", help="第一个版本。"),
    version_two: str | None = typer.Argument(None, metavar="版本2", help="第二个版本。"),
    mode: str | None = typer.Argument(
        None,
        metavar="模式",
        help=f"要比较的模式：{supported_modes_text()}。",
    ),
    node: int | None = typer.Argument(
        None,
        metavar="节点",
        min=1,
        help="角色、光锥或关卡节点序号。",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="显示角色特殊效果。",
    ),
    markdown: bool = typer.Option(
        False,
        "--markdown",
        help="以 Markdown 格式输出；省略模式时导出全部模式。",
    ),
    pdf: bool = typer.Option(
        False,
        "--pdf",
        help="以 PDF 格式输出到标准输出；省略模式时导出全部模式，请使用 > 保存文件。",
    ),
) -> None:
    """比较同一版本线中两个版本的指定模式；省略参数时进入导航向导。"""
    global MARKDOWN_OUTPUT, PDF_OUTPUT, PDF_RENDERER
    catalog = _load_data()
    if version_one is not None and version_two is not None and mode is None and (markdown or pdf):
        if markdown and pdf:
            _abort_cli("--markdown 和 --pdf 不能同时使用。")
        if pdf and sys.stdout.isatty():
            _abort_cli("--pdf 输出的是二进制数据，请使用 hvi diff 版本1 版本2 --pdf > diff.pdf。")
        previous_markdown = MARKDOWN_OUTPUT
        previous_pdf = PDF_OUTPUT
        previous_renderer = PDF_RENDERER
        MARKDOWN_OUTPUT = markdown
        PDF_OUTPUT = pdf
        PDF_RENDERER = PdfRenderer() if pdf else None
        try:
            record_one = find_release(catalog, version_one)
            record_two = find_release(catalog, version_two)
            if record_one.name != record_two.name:
                raise ValueError("两个版本必须属于同一版本组。")
            if not _render_diff_all(
                version_one,
                version_two,
                record_one,
                record_two,
                verbose,
            ):
                _print_no_changes()
            if pdf:
                _write_pdf()
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            _abort_cli(f"{error} 支持的模式：{supported_modes_text()}。")
        finally:
            MARKDOWN_OUTPUT = previous_markdown
            PDF_OUTPUT = previous_pdf
            PDF_RENDERER = previous_renderer
        return
    if version_one is None or version_two is None or mode is None:
        if not sys.stdin.isatty():
            _abort_cli("diff 缺少参数；请在交互式终端中运行 hvi diff，或补全命令参数。")
        if markdown or pdf:
            option = "--markdown" if markdown else "--pdf"
            _abort_cli(f"{option} 不能用于交互式向导，请补全 diff 参数。")
        try:
            with _terminal_output():
                _run_diff_wizard(catalog, version_one, version_two, mode, node, verbose)
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            _abort_cli(error)
        return
    if markdown and pdf:
        _abort_cli("--markdown 和 --pdf 不能同时使用。")
    if pdf and sys.stdout.isatty():
        _abort_cli("--pdf 输出的是二进制数据，请使用 hvi diff ... --pdf > diff.pdf。")
    previous_markdown = MARKDOWN_OUTPUT
    previous_pdf = PDF_OUTPUT
    previous_renderer = PDF_RENDERER
    MARKDOWN_OUTPUT = markdown
    PDF_OUTPUT = pdf
    PDF_RENDERER = PdfRenderer() if pdf else None
    try:
        record_one = find_release(catalog, version_one)
        record_two = find_release(catalog, version_two)
        mode = mode.lower()
        if mode == "character":
            if node is not None:
                reports = (
                    compare_character_versions(
                        version_one,
                        version_two,
                        node,
                        record_one,
                        record_two,
                    ),
                )
            else:
                reports = compare_all_character_versions(
                    version_one,
                    version_two,
                    record_one,
                    record_two,
                )
            all_reports = reports
            reports = all_reports if pdf else tuple(
                report
                for report in all_reports
                if any(
                    section.status != "unchanged"
                    and (verbose or section.name != "特殊效果")
                    for section in report.sections
                )
            )
            if not reports:
                _print_no_changes()
            for index, report in enumerate(reports):
                if index and not pdf:
                    console.print()
                render_character_diff(report, verbose)
        elif mode == "lightcone":
            if node is not None:
                reports = (
                    compare_lightcone_versions(
                        version_one,
                        version_two,
                        node,
                        record_one,
                        record_two,
                    ),
                )
            else:
                reports = compare_all_lightcone_versions(
                    version_one,
                    version_two,
                    record_one,
                    record_two,
                )
            all_reports = reports
            reports = all_reports if pdf else tuple(
                report for report in all_reports if report.changed_sections
            )
            if not reports:
                _print_no_changes()
            for index, report in enumerate(reports):
                if index and not pdf:
                    console.print()
                render_lightcone_diff(report)
        elif mode == "maze":
            if node is not None:
                reports = (
                    compare_maze_versions(
                        version_one,
                        version_two,
                        node,
                        record_one,
                        record_two,
                    ),
                )
            else:
                reports = compare_all_maze_versions(
                    version_one,
                    version_two,
                    record_one,
                    record_two,
                )
            all_reports = reports
            reports = all_reports if pdf else tuple(
                report for report in all_reports if report.changed_sections
            )
            if not reports:
                _print_no_changes()
            for index, report in enumerate(reports):
                if index and not pdf:
                    console.print()
                render_highmode_diff(report, index == 0)
        elif mode == "story":
            if node is not None:
                render_highmode_diff(
                    compare_highmode_versions(
                        version_one,
                        version_two,
                        mode,
                        node,
                        record_one,
                        record_two,
                    )
                )
            else:
                all_reports = tuple(
                    report
                    for report in compare_all_story_versions(
                        version_one,
                        version_two,
                        record_one,
                        record_two,
                    )
                )
                reports = all_reports if pdf else tuple(
                    report for report in all_reports if report.changed_sections
                )
                if not reports:
                    _print_no_changes()
                for index, report in enumerate(reports):
                    if index and not pdf:
                        console.print()
                    render_highmode_diff(report, index == 0)
        elif mode == "boss":
            if node is not None:
                reports = (
                    compare_boss_versions(
                        version_one,
                        version_two,
                        node,
                        record_one,
                        record_two,
                    ),
                )
            else:
                reports = compare_all_boss_versions(
                    version_one,
                    version_two,
                    record_one,
                    record_two,
                )
            all_reports = reports
            reports = all_reports if pdf else tuple(
                report for report in all_reports if report.changed_sections
            )
            if not reports:
                _print_no_changes()
            for index, report in enumerate(reports):
                if index and not pdf:
                    console.print()
                render_highmode_diff(report, index == 0)
        elif mode in {"peak", "knight", "king", "hard-king"}:
            render_highmode_diff(
                compare_highmode_versions(
                    version_one,
                    version_two,
                    mode,
                    node,
                    record_one,
                    record_two,
                )
            )
        else:
            if node is not None:
                raise ValueError("节点参数仅支持角色、光锥、末日、虚构和骑士比较。")
            render_diff(compare_versions(version_one, version_two, mode, record_one, record_two))
        if pdf:
            _write_pdf()
    except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
        _abort_cli(f"{error} 支持的模式：{supported_modes_text()}。")
    finally:
        MARKDOWN_OUTPUT = previous_markdown
        PDF_OUTPUT = previous_pdf
        PDF_RENDERER = previous_renderer


@app.command()
def show(
    version_or_mode: str | None = typer.Argument(
        None, metavar="版本或模式", help="版本，或使用 knight 调取最新异相数据。"
    ),
    mode_or_node: str | None = typer.Argument(
        None, metavar="模式或序号", help="模式，或骑士序号。"
    ),
    node: int | None = typer.Argument(
        None, metavar="节点", min=1, help="角色序号或关卡节点编号。"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="显示角色特殊效果。",
    ),
    markdown: bool = typer.Option(
        False,
        "--markdown",
        help="以 Markdown 格式输出；省略模式时导出版本的全部模式。",
    ),
    pdf: bool = typer.Option(
        False,
        "--pdf",
        help="以 PDF 格式输出到标准输出；省略模式时导出版本的全部模式，请使用 > 保存文件。",
    ),
) -> None:
    """显示角色或关卡数据；省略参数时进入导航向导。"""
    global MARKDOWN_OUTPUT, PDF_OUTPUT, PDF_RENDERER
    catalog = _load_data()
    if (
        version_or_mode is not None
        and version_or_mode != "knight"
        and mode_or_node is None
        and (markdown or pdf)
    ):
        if markdown and pdf:
            _abort_cli("--markdown 和 --pdf 不能同时使用。")
        if pdf and sys.stdout.isatty():
            _abort_cli("--pdf 输出的是二进制数据，请使用 hvi show 版本 --pdf > show.pdf。")
        previous_markdown = MARKDOWN_OUTPUT
        previous_pdf = PDF_OUTPUT
        previous_renderer = PDF_RENDERER
        MARKDOWN_OUTPUT = markdown
        PDF_OUTPUT = pdf
        PDF_RENDERER = PdfRenderer() if pdf else None
        try:
            record = find_release(catalog, version_or_mode)
            _render_show_all(version_or_mode, record, verbose)
            if pdf:
                _write_pdf()
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            _abort_cli(error)
        finally:
            MARKDOWN_OUTPUT = previous_markdown
            PDF_OUTPUT = previous_pdf
            PDF_RENDERER = previous_renderer
        return
    interactive = (
        version_or_mode is None
        or mode_or_node is None
        or (
            mode_or_node.lower() in {"character", "lightcone"}
            and node is None
        )
    )
    if interactive:
        if not sys.stdin.isatty():
            _abort_cli("show 缺少参数；请在交互式终端中运行 hvi show，或补全命令参数。")
        if markdown or pdf:
            option = "--markdown" if markdown else "--pdf"
            _abort_cli(f"{option} 不能用于交互式向导，请补全 show 参数。")
        try:
            with _terminal_output():
                _run_show_wizard(catalog, version_or_mode, mode_or_node, node, verbose)
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            _abort_cli(error)
        return
    if markdown and pdf:
        _abort_cli("--markdown 和 --pdf 不能同时使用。")
    if pdf and sys.stdout.isatty():
        _abort_cli("--pdf 输出的是二进制数据，请使用 hvi show ... --pdf > show.pdf。")
    previous_markdown = MARKDOWN_OUTPUT
    previous_pdf = PDF_OUTPUT
    previous_renderer = PDF_RENDERER
    MARKDOWN_OUTPUT = markdown
    PDF_OUTPUT = pdf
    PDF_RENDERER = PdfRenderer() if pdf else None
    try:
        if version_or_mode == "knight":
            if node is not None:
                raise ValueError("请使用 hvi show knight 1、hvi show knight 2 或 hvi show knight 3。")
            record = max(
                catalog,
                key=lambda item: max(item.versions, default=""),
            )
            version = max(record.versions)
            mode = "knight"
            if mode_or_node is not None:
                node = int(mode_or_node)
        elif mode_or_node is None:
            raise ValueError("请指定模式。")
        else:
            version = version_or_mode
            mode = mode_or_node.lower()
            record = find_release(catalog, version)

        if mode == "character":
            if node is None or not record.character:
                raise ValueError(f"版本 {version} 未配置角色资源。")
            if node > len(record.character):
                raise ValueError(
                    f"角色序号 {node} 超出范围；版本 {version} 共有 {len(record.character)} 个角色。"
                )
            render_character(
                load_character(version, record.character[node - 1]),
                verbose,
            )
        elif mode == "lightcone":
            if node is None or not record.lightcone:
                raise ValueError(f"版本 {version} 未配置光锥资源。")
            if node > len(record.lightcone):
                raise ValueError(
                    f"光锥序号 {node} 超出范围；版本 {version} 共有 {len(record.lightcone)} 个光锥。"
                )
            render_lightcone(
                load_lightcone(version, record.lightcone[node - 1])
            )
        elif mode == "maze":
            if not record.maze:
                raise ValueError(f"版本 {version} 未配置混沌资源。")
            nodes = (node,) if node is not None else available_maze_nodes(version, record.maze)
            if not nodes:
                raise ValueError(f"版本 {version} 的混沌数据中未找到节点。")
            seen_maze_buffs: set[tuple[str, str]] = set()
            for index, maze_node in enumerate(nodes):
                if index and not pdf:
                    _print_markdown([""]) if markdown else console.print()
                render_maze(
                    load_maze(version, record.maze, maze_node),
                    seen_maze_buffs,
                )
        elif mode == "boss":
            if not record.boss:
                raise ValueError(f"版本 {version} 未配置末日资源。")
            nodes = (node,) if node is not None else available_boss_nodes(version, record.boss)
            if not nodes:
                raise ValueError(f"版本 {version} 的末日数据中未找到节点。")
            for index, boss_node in enumerate(nodes):
                if index and not pdf:
                    console.print()
                render_boss(load_boss(version, record.boss, boss_node))
        elif mode == "story":
            if not record.story:
                raise ValueError(f"版本 {version} 未配置虚构资源。")
            nodes = (node,) if node is not None else available_story_nodes(version, record.story)
            if not nodes:
                raise ValueError(f"版本 {version} 的虚构数据中未找到节点。")
            for index, story_node in enumerate(nodes):
                if index and not pdf:
                    console.print()
                view = load_story(version, record.story, story_node)
                render_highmode(
                    view,
                    prelude_buffs=view.season_buffs if index == 0 else (),
                )
        elif mode in {"knight", "king", "hard-king"}:
            if not record.peak:
                raise ValueError(f"版本 {version} 未配置异相资源。")
            nodes = (node,) if node is not None else ((1, 2, 3) if mode == "knight" else (None,))
            for index, peak_node in enumerate(nodes):
                if index and not pdf:
                    console.print()
                render_highmode(load_peak(version, record.peak, mode, peak_node))
        elif mode == "peak":
            if not record.peak:
                raise ValueError(f"版本 {version} 未配置异相资源。")
            if node is None:
                sections = (
                    ("knight", 1),
                    ("knight", 2),
                    ("knight", 3),
                    ("king", None),
                    ("hard-king", None),
                )
            else:
                if node > 5:
                    raise ValueError("异相节点必须是 1 到 5。")
                peak_kind = "knight" if node <= 3 else "king" if node == 4 else "hard-king"
                sections = ((peak_kind, node if peak_kind == "knight" else None),)
            for index, (peak_kind, peak_node) in enumerate(sections):
                if index and not pdf:
                    console.print()
                render_highmode(load_peak(version, record.peak, peak_kind, peak_node))
        else:
            raise ValueError("支持的模式：角色、光锥、混沌、虚构、末日、异相、骑士、王棋和绝境。")
        if pdf:
            _write_pdf()
    except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
        _abort_cli(error)
    finally:
        MARKDOWN_OUTPUT = previous_markdown
        PDF_OUTPUT = previous_pdf
        PDF_RENDERER = previous_renderer


if __name__ == "__main__":
    app()

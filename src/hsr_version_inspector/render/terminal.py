"""Rich terminal renderer.

The application configures this module for each command so renderers do not
own Typer command state or data loading.
"""

from __future__ import annotations

import sys
from typing import Any

from rich import box
from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ..boss import BossBuff, BossView
from ..character import (
    CharacterSkill,
    CharacterText,
    CharacterView,
    group_skill_entries,
    skill_entry_title,
    skill_group_title,
)
from ..data import VersionRecord
from ..diff import (
    CharacterChange,
    CharacterDiffReport,
    DiffReport,
    HighModeChange,
    HighModeDiffReport,
    LightConeChange,
    LightConeDiffReport,
    character_change_subject,
    format_name_change,
    format_value,
    highmode_change_subject,
    highmode_change_wave,
    is_missing,
)
from ..highmode import HighModeView, MazeView
from ..lightcone import LightConeView
from ..output.diff_markup import (
    lightcone_text_markup as _lightcone_text_markup,
)
from ..output.diff_markup import (
    rich_text_diff_markup as _rich_text_diff_markup,
)
from ..output.diff_markup import (
    shared_text_arrow_markup as _shared_text_arrow_markup,
)
from ..output.diff_markup import (
    shared_text_markup as _shared_text_markup,
)
from ..output.labels import STATUS_LABELS
from ..output.labels import element_label as _element_label
from ..output.labels import mode_label as _mode_label
from ..output.text import (
    enemy_count_text as _enemy_count_text,
)
from ..output.text import (
    markdown_text as _markdown_text,
)
from ..output.text import (
    terminal_text as _terminal_text,
)
from ..output.text import (
    unique_by_name_and_description as _unique_buffs,
)
from .markdown import _highmode_section_label
from .markdown import (
    boss as _markdown_boss,
)
from .markdown import (
    catalog as _markdown_catalog,
)
from .markdown import (
    character as _markdown_character,
)
from .markdown import (
    character_diff as _markdown_character_diff,
)
from .markdown import (
    diff as _markdown_diff,
)
from .markdown import (
    highmode as _markdown_highmode,
)
from .markdown import (
    highmode_diff as _markdown_highmode_diff,
)
from .markdown import (
    lightcone as _markdown_lightcone,
)
from .markdown import (
    lightcone_diff as _markdown_lightcone_diff,
)

console = Console()
MARKDOWN_OUTPUT = False
PDF_OUTPUT = False
PDF_RENDERER: Any = None


def _highmode_metadata_label(label: str) -> str:
    return {"Title": "名称", "Level": "等级"}.get(label, label)


def configure(
    *,
    console_obj: Console,
    markdown: bool,
    pdf: bool,
    pdf_renderer: Any,
    print_markdown: Any,
) -> None:
    global console, MARKDOWN_OUTPUT, PDF_OUTPUT, PDF_RENDERER, _print_markdown
    console = console_obj
    MARKDOWN_OUTPUT = markdown
    PDF_OUTPUT = pdf
    PDF_RENDERER = pdf_renderer
    _print_markdown = print_markdown


def _print_markdown(lines: list[str]) -> None:
    sys.stdout.write("\n".join(lines).rstrip() + "\n")


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
    summary.add_row("命途", view.path)
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


def _character_change_sort_key(change: CharacterChange) -> tuple[int, str]:
    priority = {"removed": 0, "added": 1, "changed": 2}
    return priority.get(change.kind, 3), change.label


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

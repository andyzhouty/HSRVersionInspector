from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from typing import Any, NoReturn, cast

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typer import rich_utils

from . import navigation
from .boss import BossBuff, BossView, available_boss_nodes, load_boss
from .character import CharacterView, load_character
from .commands.batch import (
    BatchRenderContext,
)
from .commands.batch import (
    render_diff_all as _render_diff_all_command,
)
from .commands.batch import (
    render_show_all as _render_show_all_command,
)
from .commands.diff import diff
from .commands.download import cleanup_command, download_command
from .commands.list import list_versions
from .commands.query import query
from .commands.root import main
from .commands.show import show
from .data import (
    FullCatalog,
    VersionRecord,
    find_release,
    load_catalog,
    load_full_catalog,
)
from .diff import (
    CharacterDiffReport,
    DiffReport,
    HighModeDiffReport,
    LightConeDiffReport,
)
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
from .output.diff_markup import (
    lightcone_text_markup as _lightcone_text_markup,
)
from .output.diff_markup import (
    markdown_shared_text_markup as _markdown_shared_text_markup,
)
from .output.diff_markup import (
    shared_text_markup as _shared_text_markup,
)
from .output.labels import mode_label as _mode_label
from .output.text import enemy_count_text as _enemy_count_text
from .pdf import PdfRenderer
from .render import terminal as terminal_renderer
from .render.markdown import (
    highmode as _markdown_highmode,
)

__all__ = [
    "_enemy_count_text",
    "_lightcone_text_markup",
    "_markdown_highmode",
    "_markdown_shared_text_markup",
    "_shared_text_markup",
    "cleanup_command",
    "diff",
    "download_command",
    "find_release",
    "list_versions",
    "main",
    "query",
    "show",
]


rich_utils.ARGUMENTS_PANEL_TITLE = "参数"
rich_utils.COMMANDS_PANEL_TITLE = "命令"
rich_utils.ERRORS_PANEL_TITLE = "错误"
rich_utils.OPTIONS_PANEL_TITLE = "选项"
rich_utils.REQUIRED_LONG_STRING = "[必填]"

try:
    from typer._click import decorators as _typer_decorators
    from typer._click.formatting import HelpFormatter as _TyperHelpFormatter

    _decorators = cast(Any, _typer_decorators)
    _formatter = cast(Any, _TyperHelpFormatter)
    _default_help_option = _decorators.help_option

    def _chinese_help_option(param_decls: list[str]) -> Any:
        decorator = _default_help_option(param_decls)

        def apply_help_option(command: Any) -> Any:
            result = decorator(command)
            result.params[-1].help = "显示帮助信息并退出。"
            return result

        return apply_help_option

    _decorators.help_option = _chinese_help_option
    _default_write_usage = _formatter.write_usage

    def _write_chinese_usage(
        self: Any,
        prog: str,
        args: str = "",
        prefix: str | None = None,
    ) -> Any:
        return _default_write_usage(self, prog, args, prefix or "用法：")

    _formatter.write_usage = _write_chinese_usage
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


def _print_markdown(lines: list[str]) -> None:
    sys.stdout.write("\n".join(lines).rstrip() + "\n")


def _print_no_changes() -> None:
    if PDF_OUTPUT and PDF_RENDERER is not None:
        PDF_RENDERER.add_no_changes()
    elif MARKDOWN_OUTPUT:
        _print_markdown(["未发现变更。"])
    else:
        console.print("[dim]未发现变更。[/dim]")


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


def _abort_cli(message: object) -> NoReturn:
    console.print(f"[red]错误：{message}[/red]")
    raise typer.Exit(code=1)


def _configure_terminal_renderer() -> None:
    terminal_renderer.configure(
        console_obj=console,
        markdown=MARKDOWN_OUTPUT,
        pdf=PDF_OUTPUT,
        pdf_renderer=PDF_RENDERER,
        print_markdown=_print_markdown,
    )


def catalog_table(catalog: tuple[VersionRecord, ...], numbered: bool = False) -> Table:
    _configure_terminal_renderer()
    return terminal_renderer.catalog_table(catalog, numbered)


def detail_panel(record: VersionRecord) -> Panel:
    _configure_terminal_renderer()
    return terminal_renderer.detail_panel(record)


def render_catalog(catalog: tuple[VersionRecord, ...]) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_catalog(catalog)


def render_batch_error(title: str, error: object) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_batch_error(title, error)


def render_boss(view: BossView, title: str | None = None) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_boss(view, title)


def render_character(view: CharacterView, verbose: bool = False) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_character(view, verbose)


def render_lightcone(view: LightConeView) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_lightcone(view)


def render_highmode(
    view: HighModeView,
    title: str | None = None,
    stage_buffs: tuple[BossBuff, ...] | None = None,
    prelude_buffs: tuple[BossBuff, ...] | None = None,
) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_highmode(view, title, stage_buffs, prelude_buffs)


def render_maze(view: MazeView, seen_buffs: set[tuple[str, str]]) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_maze(view, seen_buffs)


def render_diff(report: DiffReport) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_diff(report)


def render_character_diff(report: CharacterDiffReport, verbose: bool = False) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_character_diff(report, verbose)


def render_lightcone_diff(report: LightConeDiffReport) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_lightcone_diff(report)


def render_highmode_diff(
    report: HighModeDiffReport, include_header: bool = True
) -> None:
    _configure_terminal_renderer()
    terminal_renderer.render_highmode_diff(report, include_header)


def _configure_navigation() -> None:
    navigation.configure(
        console_obj=console,
        load_full_data=_load_full_data,
        render_catalog=render_catalog,
        detail_panel=detail_panel,
        show=show,
        diff=diff,
        query=query,
        available_boss_nodes_fn=available_boss_nodes,
        available_maze_nodes_fn=available_maze_nodes,
        available_story_nodes_fn=available_story_nodes,
        prompt_index=_prompt_index,
        prompt_record=_prompt_record,
        prompt_release=_prompt_release,
        prompt_full_resource_id=_prompt_full_resource_id,
        pause_interactive_result=_pause_interactive_result,
    )


def _choice_table(
    title: str, options: tuple[tuple[str, str], ...], *, all_label: str | None = None
) -> Table:
    return navigation.default_choice_table(title, options, all_label=all_label)


def _prompt_index(
    title: str, options: tuple[tuple[str, str], ...], *, all_label: str | None = None
) -> int | None:
    return navigation.default_prompt_index(title, options, all_label=all_label)


def _prompt_record(
    catalog: tuple[VersionRecord, ...], title: str = "选择版本组"
) -> VersionRecord | None:
    return navigation.default_prompt_record(catalog, title)


def _prompt_release(
    record: VersionRecord, title: str, *, excluded: frozenset[str] = frozenset()
) -> str | None:
    return navigation.default_prompt_release(record, title, excluded=excluded)


def _pause_interactive_result() -> None:
    navigation.default_pause_interactive_result()


def _query_mode_options() -> tuple[tuple[str, str], ...]:
    return navigation._query_mode_options()


def _query_resource_mode(mode: str) -> str:
    return navigation._query_resource_mode(mode)


def _prompt_full_resource_id(full_catalog: FullCatalog, mode: str) -> int | None:
    return navigation.default_prompt_full_resource_id(full_catalog, mode)


def _show_mode_options(record: VersionRecord) -> tuple[tuple[str, str], ...]:
    return navigation._show_mode_options(record)


def _diff_mode_options(
    record_one: VersionRecord, record_two: VersionRecord
) -> tuple[tuple[str, str], ...]:
    return navigation._diff_mode_options(record_one, record_two)


def _run_show_wizard(
    catalog: tuple[VersionRecord, ...],
    version_or_mode: str | None = None,
    mode_or_node: str | None = None,
    node: int | None = None,
    verbose: bool = False,
) -> None:
    _configure_navigation()
    navigation._run_show_wizard(catalog, version_or_mode, mode_or_node, node, verbose)


def _run_diff_wizard(
    catalog: tuple[VersionRecord, ...],
    version_one: str | None = None,
    version_two: str | None = None,
    mode: str | None = None,
    node: int | None = None,
    verbose: bool = False,
) -> None:
    _configure_navigation()
    navigation._run_diff_wizard(catalog, version_one, version_two, mode, node, verbose)


def _run_query_wizard(
    catalog: tuple[VersionRecord, ...],
    mode: str | None = None,
    resource_id: int | None = None,
    node: int | None = None,
    verbose: bool = False,
) -> None:
    _configure_navigation()
    navigation._run_query_wizard(catalog, mode, resource_id, node, verbose)


def _run_catalog_browser(catalog: tuple[VersionRecord, ...]) -> None:
    _configure_navigation()
    navigation._run_catalog_browser(catalog)


def _run_tui(catalog: tuple[VersionRecord, ...]) -> None:
    _configure_navigation()
    navigation._run_tui(catalog)


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


def _batch_context() -> BatchRenderContext:
    register = None
    if PDF_OUTPUT and PDF_RENDERER is not None:
        register = getattr(PDF_RENDERER, "register_diff_overview", None)
    return BatchRenderContext(
        available_maze_nodes=available_maze_nodes,
        available_story_nodes=available_story_nodes,
        available_boss_nodes=available_boss_nodes,
        load_character=load_character,
        load_lightcone=load_lightcone,
        load_maze=load_maze,
        load_story=load_story,
        load_boss=load_boss,
        load_peak=load_peak,
        render_character=render_character,
        render_lightcone=render_lightcone,
        render_maze=render_maze,
        render_highmode=render_highmode,
        render_boss=render_boss,
        render_character_diff=render_character_diff,
        render_lightcone_diff=render_lightcone_diff,
        render_highmode_diff=render_highmode_diff,
        render_batch_error=render_batch_error,
        batch_separator=_batch_separator,
        begin_pdf_mode=_begin_pdf_mode,
        begin_pdf_diff_mode=_begin_pdf_diff_mode,
        register_diff_overview=register,
        mode_label=_mode_label,
        pdf_output=PDF_OUTPUT,
        pdf_renderer=PDF_RENDERER,
    )


def _render_show_all(version: str, record: VersionRecord, verbose: bool) -> None:
    _render_show_all_command(version, record, verbose, _batch_context())


def _render_diff_all(
    version_one: str,
    version_two: str,
    record_one: VersionRecord,
    record_two: VersionRecord,
    verbose: bool,
) -> bool:
    return _render_diff_all_command(
        version_one,
        version_two,
        record_one,
        record_two,
        verbose,
        _batch_context(),
    )

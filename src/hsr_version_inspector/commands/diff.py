"""Single-mode diff routing."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import typer

from ..data import VersionRecord
from ..diff import (
    compare_all_boss_versions,
    compare_all_character_versions,
    compare_all_lightcone_versions,
    compare_all_maze_versions,
    compare_all_story_versions,
    compare_boss_versions,
    compare_character_versions,
    compare_highmode_versions,
    compare_lightcone_versions,
    compare_maze_versions,
    compare_versions,
    supported_modes_text,
)
from .runtime import app_module


@dataclass(frozen=True)
class DiffContext:
    render_diff: Any
    render_character_diff: Any
    render_lightcone_diff: Any
    render_highmode_diff: Any
    console: Any
    print_markdown: Any
    print_no_changes: Any
    markdown_output: bool
    pdf_output: bool


def register(app: typer.Typer, command: Callable[..., Any]) -> None:
    app.command()(command)


def _render_diff_mode(
    version_one: str,
    version_two: str,
    mode: str,
    node: int | None,
    verbose: bool,
    record_one: VersionRecord,
    record_two: VersionRecord,
    context: DiffContext,
) -> None:
    render_diff_mode(
        version_one,
        version_two,
        mode,
        node,
        verbose,
        record_one,
        record_two,
        context,
    )


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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示角色特殊效果。"),
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
    runtime = app_module()
    catalog = runtime._load_data()
    if version_one is not None and version_two is not None and mode is None and (markdown or pdf):
        if markdown and pdf:
            runtime._abort_cli("--markdown 和 --pdf 不能同时使用。")
        if pdf and sys.stdout.isatty():
            runtime._abort_cli("--pdf 输出的是二进制数据，请使用 hvi diff 版本1 版本2 --pdf > diff.pdf。")
        previous_markdown = runtime.MARKDOWN_OUTPUT
        previous_pdf = runtime.PDF_OUTPUT
        previous_renderer = runtime.PDF_RENDERER
        runtime.MARKDOWN_OUTPUT = markdown
        runtime.PDF_OUTPUT = pdf
        runtime.PDF_RENDERER = runtime.PdfRenderer() if pdf else None
        try:
            record_one = runtime.find_release(catalog, version_one)
            record_two = runtime.find_release(catalog, version_two)
            if record_one.name != record_two.name:
                raise ValueError("两个版本必须属于同一版本组。")
            if not runtime._render_diff_all(
                version_one,
                version_two,
                record_one,
                record_two,
                verbose,
            ):
                runtime._print_no_changes()
            if pdf:
                runtime._write_pdf()
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            runtime._abort_cli(f"{error} 支持的模式：{supported_modes_text()}。")
        finally:
            runtime.MARKDOWN_OUTPUT = previous_markdown
            runtime.PDF_OUTPUT = previous_pdf
            runtime.PDF_RENDERER = previous_renderer
        return
    if version_one is None or version_two is None or mode is None:
        if not sys.stdin.isatty():
            runtime._abort_cli("diff 缺少参数；请在交互式终端中运行 hvi diff，或补全命令参数。")
        if markdown or pdf:
            option = "--markdown" if markdown else "--pdf"
            runtime._abort_cli(f"{option} 不能用于交互式向导，请补全 diff 参数。")
        try:
            with runtime._terminal_output():
                runtime._run_diff_wizard(catalog, version_one, version_two, mode, node, verbose)
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            runtime._abort_cli(error)
        return
    if markdown and pdf:
        runtime._abort_cli("--markdown 和 --pdf 不能同时使用。")
    if pdf and sys.stdout.isatty():
        runtime._abort_cli("--pdf 输出的是二进制数据，请使用 hvi diff ... --pdf > diff.pdf。")
    previous_markdown = runtime.MARKDOWN_OUTPUT
    previous_pdf = runtime.PDF_OUTPUT
    previous_renderer = runtime.PDF_RENDERER
    runtime.MARKDOWN_OUTPUT = markdown
    runtime.PDF_OUTPUT = pdf
    runtime.PDF_RENDERER = runtime.PdfRenderer() if pdf else None
    try:
        record_one = runtime.find_release(catalog, version_one)
        record_two = runtime.find_release(catalog, version_two)
        mode = mode.lower()
        _render_diff_mode(
            version_one,
            version_two,
            mode,
            node,
            verbose,
            record_one,
            record_two,
            DiffContext(
                render_diff=runtime.render_diff,
                render_character_diff=runtime.render_character_diff,
                render_lightcone_diff=runtime.render_lightcone_diff,
                render_highmode_diff=runtime.render_highmode_diff,
                console=runtime.console,
                print_markdown=runtime._print_markdown,
                print_no_changes=runtime._print_no_changes,
                markdown_output=runtime.MARKDOWN_OUTPUT,
                pdf_output=runtime.PDF_OUTPUT,
            ),
        )
        if pdf:
            runtime._write_pdf()
    except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
        runtime._abort_cli(f"{error} 支持的模式：{supported_modes_text()}。")
    finally:
        runtime.MARKDOWN_OUTPUT = previous_markdown
        runtime.PDF_OUTPUT = previous_pdf
        runtime.PDF_RENDERER = previous_renderer


def _separator(context: DiffContext) -> None:
    if context.pdf_output:
        return
    context.print_markdown([""]) if context.markdown_output else context.console.print()


def render_diff_mode(
    version_one: str,
    version_two: str,
    mode: str,
    node: int | None,
    verbose: bool,
    record_one: VersionRecord,
    record_two: VersionRecord,
    context: DiffContext,
) -> None:
    if mode == "character":
        reports = (
            (compare_character_versions(version_one, version_two, node, record_one, record_two),)
            if node is not None
            else compare_all_character_versions(version_one, version_two, record_one, record_two)
        )
        reports = reports if context.pdf_output else tuple(
            report for report in reports
            if any(section.status != "unchanged" and (verbose or section.name != "特殊效果") for section in report.sections)
        )
        if not reports:
            context.print_no_changes()
        for index, report in enumerate(reports):
            if index:
                _separator(context)
            context.render_character_diff(report, verbose)
        return
    if mode == "lightcone":
        reports = (
            (compare_lightcone_versions(version_one, version_two, node, record_one, record_two),)
            if node is not None
            else compare_all_lightcone_versions(version_one, version_two, record_one, record_two)
        )
        reports = reports if context.pdf_output else tuple(report for report in reports if report.changed_sections)
        if not reports:
            context.print_no_changes()
        for index, report in enumerate(reports):
            if index:
                _separator(context)
            context.render_lightcone_diff(report)
        return
    if mode == "maze":
        reports = (
            (compare_maze_versions(version_one, version_two, node, record_one, record_two),)
            if node is not None
            else compare_all_maze_versions(version_one, version_two, record_one, record_two)
        )
        reports = reports if context.pdf_output else tuple(report for report in reports if report.changed_sections)
        if not reports:
            context.print_no_changes()
        for index, report in enumerate(reports):
            if index:
                _separator(context)
            context.render_highmode_diff(report, index == 0)
        return
    if mode == "story":
        if node is not None:
            context.render_highmode_diff(compare_highmode_versions(version_one, version_two, mode, node, record_one, record_two))
            return
        reports = compare_all_story_versions(version_one, version_two, record_one, record_two)
        reports = reports if context.pdf_output else tuple(report for report in reports if report.changed_sections)
        if not reports:
            context.print_no_changes()
        for index, report in enumerate(reports):
            if index:
                _separator(context)
            context.render_highmode_diff(report, index == 0)
        return
    if mode == "boss":
        reports = (
            (compare_boss_versions(version_one, version_two, node, record_one, record_two),)
            if node is not None
            else compare_all_boss_versions(version_one, version_two, record_one, record_two)
        )
        reports = reports if context.pdf_output else tuple(report for report in reports if report.changed_sections)
        if not reports:
            context.print_no_changes()
        for index, report in enumerate(reports):
            if index:
                _separator(context)
            context.render_highmode_diff(report, index == 0)
        return
    if mode in {"peak", "knight", "king", "hard-king"}:
        context.render_highmode_diff(compare_highmode_versions(version_one, version_two, mode, node, record_one, record_two))
        return
    if node is not None:
        raise ValueError("节点参数仅支持角色、光锥、末日、虚构和骑士比较。")
    context.render_diff(compare_versions(version_one, version_two, mode, record_one, record_two))

"""Resource routing for full-data and latest-version queries."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import typer

from ..data import latest_release
from .runtime import app_module


@dataclass(frozen=True)
class QueryContext:
    load_character: Any
    load_lightcone: Any
    load_maze: Any
    load_story: Any
    load_boss: Any
    load_peak: Any
    available_maze_nodes: Any
    available_story_nodes: Any
    available_boss_nodes: Any
    render_character: Any
    render_lightcone: Any
    render_maze: Any
    render_highmode: Any
    render_boss: Any
    console: Any
    print_markdown: Any
    markdown_output: bool
    pdf_output: bool
    mode_label: Any


def register(app: typer.Typer, command: Callable[..., Any]) -> None:
    app.command()(command)


def _render_query(
    version: str,
    mode: str,
    resource_id: int,
    node: int | None,
    verbose: bool,
    context: QueryContext,
) -> None:
    render_query(version, mode, resource_id, node, verbose, context)


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
    runtime = app_module()
    catalog = runtime._load_data()
    if mode is None or resource_id is None:
        if not sys.stdin.isatty():
            runtime._abort_cli("query 缺少参数；请提供模式和数据 ID。")
        if markdown or pdf:
            option = "--markdown" if markdown else "--pdf"
            runtime._abort_cli(f"{option} 不能用于交互式向导，请补全 query 参数。")
        try:
            with runtime._terminal_output():
                runtime._run_query_wizard(catalog, mode, resource_id, node, verbose)
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            runtime._abort_cli(error)
        return
    if markdown and pdf:
        runtime._abort_cli("--markdown 和 --pdf 不能同时使用。")
    if pdf and sys.stdout.isatty():
        runtime._abort_cli("--pdf 输出的是二进制数据，请使用 hvi query ... --pdf > query.pdf。")

    previous_markdown = runtime.MARKDOWN_OUTPUT
    previous_pdf = runtime.PDF_OUTPUT
    previous_renderer = runtime.PDF_RENDERER
    runtime.MARKDOWN_OUTPUT = markdown
    runtime.PDF_OUTPUT = pdf
    runtime.PDF_RENDERER = runtime.PdfRenderer() if pdf else None
    try:
        mode = mode.lower()
        resource_mode = runtime._query_resource_mode(mode)
        full_catalog = runtime._load_full_data()
        if mode not in {value for value, _ in runtime._query_mode_options()}:
            raise ValueError(f"不支持的查询模式 {mode!r}。")
        if not full_catalog.contains(resource_mode, resource_id):
            raise ValueError(
                f"{runtime._mode_label(resource_mode)}数据 ID {resource_id} 不在 full.json 中。"
            )
        version = latest_release(catalog)
        _render_query(
            version,
            mode,
            resource_id,
            node,
            verbose,
            QueryContext(
                load_character=runtime.load_character,
                load_lightcone=runtime.load_lightcone,
                load_maze=runtime.load_maze,
                load_story=runtime.load_story,
                load_boss=runtime.load_boss,
                load_peak=runtime.load_peak,
                available_maze_nodes=runtime.available_maze_nodes,
                available_story_nodes=runtime.available_story_nodes,
                available_boss_nodes=runtime.available_boss_nodes,
                render_character=runtime.render_character,
                render_lightcone=runtime.render_lightcone,
                render_maze=runtime.render_maze,
                render_highmode=runtime.render_highmode,
                render_boss=runtime.render_boss,
                console=runtime.console,
                print_markdown=runtime._print_markdown,
                markdown_output=runtime.MARKDOWN_OUTPUT,
                pdf_output=runtime.PDF_OUTPUT,
                mode_label=runtime._mode_label,
            ),
        )
        if pdf:
            runtime._write_pdf()
    except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
        runtime._abort_cli(f"{error} 请先运行 hvi download。")
    finally:
        runtime.MARKDOWN_OUTPUT = previous_markdown
        runtime.PDF_OUTPUT = previous_pdf
        runtime.PDF_RENDERER = previous_renderer


def render_query(
    version: str,
    mode: str,
    resource_id: int,
    node: int | None,
    verbose: bool,
    context: QueryContext,
) -> None:
    resource = str(resource_id)
    if mode == "character":
        if node is not None:
            raise ValueError("角色查询不接受节点参数。")
        context.render_character(context.load_character(version, resource), verbose)
        return
    if mode == "lightcone":
        if node is not None:
            raise ValueError("光锥查询不接受节点参数。")
        context.render_lightcone(context.load_lightcone(version, resource))
        return
    if mode == "maze":
        nodes = (node,) if node is not None else context.available_maze_nodes(version, resource)
        if not nodes:
            raise ValueError(f"混沌数据 {resource} 中未找到节点。")
        seen_buffs: set[tuple[str, str]] = set()
        for index, maze_node in enumerate(nodes):
            if index and not context.pdf_output:
                context.print_markdown([""]) if context.markdown_output else context.console.print()
            context.render_maze(context.load_maze(version, resource, maze_node), seen_buffs)
        return
    if mode == "boss":
        nodes = (node,) if node is not None else context.available_boss_nodes(version, resource)
        if not nodes:
            raise ValueError(f"末日数据 {resource} 中未找到节点。")
        for index, boss_node in enumerate(nodes):
            if index and not context.pdf_output:
                context.print_markdown([""]) if context.markdown_output else context.console.print()
            context.render_boss(context.load_boss(version, resource, boss_node))
        return
    if mode == "story":
        nodes = (node,) if node is not None else context.available_story_nodes(version, resource)
        if not nodes:
            raise ValueError(f"虚构数据 {resource} 中未找到节点。")
        for index, story_node in enumerate(nodes):
            if index and not context.pdf_output:
                context.print_markdown([""]) if context.markdown_output else context.console.print()
            view = context.load_story(version, resource, story_node)
            context.render_highmode(view, prelude_buffs=view.season_buffs if index == 0 else ())
        return
    if mode == "knight":
        nodes = (node,) if node is not None else (1, 2, 3)
        for index, knight_node in enumerate(nodes):
            if knight_node not in (1, 2, 3):
                raise ValueError("骑士节点必须是 1、2 或 3。")
            if index and not context.pdf_output:
                context.print_markdown([""]) if context.markdown_output else context.console.print()
            context.render_highmode(context.load_peak(version, resource, "knight", knight_node))
        return
    if mode in {"king", "hard-king"}:
        if node is not None:
            raise ValueError(f"{context.mode_label(mode)}查询不接受节点参数。")
        context.render_highmode(context.load_peak(version, resource, mode, None))
        return
    if mode == "peak":
        if node is None:
            sections = (("knight", 1), ("knight", 2), ("knight", 3), ("king", None), ("hard-king", None))
        else:
            if node > 5:
                raise ValueError("异相节点必须是 1 到 5。")
            peak_mode = "knight" if node <= 3 else "king" if node == 4 else "hard-king"
            sections = ((peak_mode, node if peak_mode == "knight" else None),)
        for index, (peak_mode, peak_node) in enumerate(sections):
            if index and not context.pdf_output:
                context.print_markdown([""]) if context.markdown_output else context.console.print()
            context.render_highmode(context.load_peak(version, resource, peak_mode, peak_node))
        return
    raise ValueError("支持的查询模式：角色、光锥、混沌、虚构、末日、异相、骑士、王棋和绝境。")

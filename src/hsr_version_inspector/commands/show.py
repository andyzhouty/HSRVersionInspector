"""Single-resource show routing."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import typer

from ..data import VersionRecord
from .runtime import app_module


@dataclass(frozen=True)
class ShowContext:
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


def register(app: typer.Typer, command: Callable[..., Any]) -> None:
    app.command()(command)


def _show_resource(
    catalog: tuple[VersionRecord, ...],
    version_or_mode: str,
    mode_or_node: str,
    node: int | None,
    verbose: bool,
    context: ShowContext,
) -> None:
    show_resource(catalog, version_or_mode, mode_or_node, node, verbose, context)


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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示角色特殊效果。"),
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
    runtime = app_module()
    catalog = runtime._load_data()
    if (
        version_or_mode is not None
        and version_or_mode != "knight"
        and mode_or_node is None
        and (markdown or pdf)
    ):
        if markdown and pdf:
            runtime._abort_cli("--markdown 和 --pdf 不能同时使用。")
        if pdf and sys.stdout.isatty():
            runtime._abort_cli("--pdf 输出的是二进制数据，请使用 hvi show 版本 --pdf > show.pdf。")
        previous_markdown = runtime.MARKDOWN_OUTPUT
        previous_pdf = runtime.PDF_OUTPUT
        previous_renderer = runtime.PDF_RENDERER
        runtime.MARKDOWN_OUTPUT = markdown
        runtime.PDF_OUTPUT = pdf
        runtime.PDF_RENDERER = runtime.PdfRenderer() if pdf else None
        try:
            record = runtime.find_release(catalog, version_or_mode)
            runtime._render_show_all(version_or_mode, record, verbose)
            if pdf:
                runtime._write_pdf()
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            runtime._abort_cli(error)
        finally:
            runtime.MARKDOWN_OUTPUT = previous_markdown
            runtime.PDF_OUTPUT = previous_pdf
            runtime.PDF_RENDERER = previous_renderer
        return
    interactive = (
        version_or_mode is None
        or mode_or_node is None
        or (mode_or_node.lower() in {"character", "lightcone"} and node is None)
    )
    if interactive:
        if not sys.stdin.isatty():
            runtime._abort_cli("show 缺少参数；请在交互式终端中运行 hvi show，或补全命令参数。")
        if markdown or pdf:
            option = "--markdown" if markdown else "--pdf"
            runtime._abort_cli(f"{option} 不能用于交互式向导，请补全 show 参数。")
        try:
            with runtime._terminal_output():
                runtime._run_show_wizard(catalog, version_or_mode, mode_or_node, node, verbose)
        except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
            runtime._abort_cli(error)
        return
    if markdown and pdf:
        runtime._abort_cli("--markdown 和 --pdf 不能同时使用。")
    if pdf and sys.stdout.isatty():
        runtime._abort_cli("--pdf 输出的是二进制数据，请使用 hvi show ... --pdf > show.pdf。")
    previous_markdown = runtime.MARKDOWN_OUTPUT
    previous_pdf = runtime.PDF_OUTPUT
    previous_renderer = runtime.PDF_RENDERER
    runtime.MARKDOWN_OUTPUT = markdown
    runtime.PDF_OUTPUT = pdf
    runtime.PDF_RENDERER = runtime.PdfRenderer() if pdf else None
    try:
        if version_or_mode is None or mode_or_node is None:
            runtime._abort_cli("show 缺少版本和模式参数。")
        assert version_or_mode is not None
        assert mode_or_node is not None
        _show_resource(
            catalog,
            version_or_mode,
            mode_or_node,
            node,
            verbose,
            ShowContext(
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
            ),
        )
        if pdf:
            runtime._write_pdf()
    except (KeyError, OSError, ValueError, json.JSONDecodeError, TypeError) as error:
        runtime._abort_cli(error)
    finally:
        runtime.MARKDOWN_OUTPUT = previous_markdown
        runtime.PDF_OUTPUT = previous_pdf
        runtime.PDF_RENDERER = previous_renderer


def show_resource(
    catalog: tuple[VersionRecord, ...],
    version_or_mode: str,
    mode_or_node: str,
    node: int | None,
    verbose: bool,
    context: ShowContext,
) -> None:
    if version_or_mode == "knight":
        if node is not None:
            raise ValueError("请使用 hvi show knight 1、hvi show knight 2 或 hvi show knight 3。")
        record = max(catalog, key=lambda item: max(item.versions, default=""))
        version = max(record.versions)
        mode = "knight"
        if mode_or_node is not None:
            node = int(mode_or_node)
    else:
        version = version_or_mode
        mode = mode_or_node.lower()
        record = app_module().find_release(catalog, version)

    if mode == "character":
        if node is None or not record.character:
            raise ValueError(f"版本 {version} 未配置角色资源。")
        if node > len(record.character):
            raise ValueError(f"角色序号 {node} 超出范围；版本 {version} 共有 {len(record.character)} 个角色。")
        context.render_character(context.load_character(version, record.character[node - 1]), verbose)
    elif mode == "lightcone":
        if node is None or not record.lightcone:
            raise ValueError(f"版本 {version} 未配置光锥资源。")
        if node > len(record.lightcone):
            raise ValueError(f"光锥序号 {node} 超出范围；版本 {version} 共有 {len(record.lightcone)} 个光锥。")
        context.render_lightcone(context.load_lightcone(version, record.lightcone[node - 1]))
    elif mode == "maze":
        if not record.maze:
            raise ValueError(f"版本 {version} 未配置混沌资源。")
        nodes = (node,) if node is not None else context.available_maze_nodes(version, record.maze)
        if not nodes:
            raise ValueError(f"版本 {version} 的混沌数据中未找到节点。")
        seen_buffs: set[tuple[str, str]] = set()
        for index, maze_node in enumerate(nodes):
            if index and not context.pdf_output:
                context.print_markdown([""]) if context.markdown_output else context.console.print()
            context.render_maze(context.load_maze(version, record.maze, maze_node), seen_buffs)
    elif mode == "boss":
        if not record.boss:
            raise ValueError(f"版本 {version} 未配置末日资源。")
        nodes = (node,) if node is not None else context.available_boss_nodes(version, record.boss)
        if not nodes:
            raise ValueError(f"版本 {version} 的末日数据中未找到节点。")
        for index, boss_node in enumerate(nodes):
            if index and not context.pdf_output:
                context.console.print()
            context.render_boss(context.load_boss(version, record.boss, boss_node))
    elif mode == "story":
        if not record.story:
            raise ValueError(f"版本 {version} 未配置虚构资源。")
        nodes = (node,) if node is not None else context.available_story_nodes(version, record.story)
        if not nodes:
            raise ValueError(f"版本 {version} 的虚构数据中未找到节点。")
        for index, story_node in enumerate(nodes):
            if index and not context.pdf_output:
                context.console.print()
            view = context.load_story(version, record.story, story_node)
            context.render_highmode(view, prelude_buffs=view.season_buffs if index == 0 else ())
    elif mode in {"knight", "king", "hard-king"}:
        if not record.peak:
            raise ValueError(f"版本 {version} 未配置异相资源。")
        nodes = (node,) if node is not None else ((1, 2, 3) if mode == "knight" else (None,))
        for index, peak_node in enumerate(nodes):
            if index and not context.pdf_output:
                context.console.print()
            context.render_highmode(context.load_peak(version, record.peak, mode, peak_node))
    elif mode == "peak":
        if not record.peak:
            raise ValueError(f"版本 {version} 未配置异相资源。")
        if node is None:
            sections = (("knight", 1), ("knight", 2), ("knight", 3), ("king", None), ("hard-king", None))
        else:
            if node > 5:
                raise ValueError("异相节点必须是 1 到 5。")
            peak_kind = "knight" if node <= 3 else "king" if node == 4 else "hard-king"
            sections = ((peak_kind, node if peak_kind == "knight" else None),)
        for index, (peak_kind, peak_node) in enumerate(sections):
            if index and not context.pdf_output:
                context.console.print()
            context.render_highmode(context.load_peak(version, record.peak, peak_kind, peak_node))
    else:
        raise ValueError("支持的模式：角色、光锥、混沌、虚构、末日、异相、骑士、王棋和绝境。")

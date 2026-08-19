"""Version-list command."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

import typer

from .runtime import app_module


def register(app: typer.Typer, command: Callable[..., Any]) -> None:
    app.command("list")(command)


def list_versions(
    markdown: bool = typer.Option(False, "--markdown", help="以 Markdown 格式输出。"),
    pdf: bool = typer.Option(False, "--pdf", help="以 PDF 格式输出到标准输出。请使用 > 保存文件。"),
) -> None:
    """打印目录中的所有版本组。"""
    runtime = app_module()
    if markdown and pdf:
        runtime._abort_cli("--markdown 和 --pdf 不能同时使用。")
    if pdf and sys.stdout.isatty():
        runtime._abort_cli("--pdf 输出的是二进制数据，请使用 hvi list --pdf > versions.pdf。")
    previous_markdown = runtime.MARKDOWN_OUTPUT
    previous_pdf = runtime.PDF_OUTPUT
    previous_renderer = runtime.PDF_RENDERER
    runtime.MARKDOWN_OUTPUT = markdown
    runtime.PDF_OUTPUT = pdf
    runtime.PDF_RENDERER = runtime.PdfRenderer() if pdf else None
    try:
        runtime.render_catalog(runtime._load_data())
        if pdf:
            runtime._write_pdf()
    finally:
        runtime.MARKDOWN_OUTPUT = previous_markdown
        runtime.PDF_OUTPUT = previous_pdf
        runtime.PDF_RENDERER = previous_renderer

"""Root command and interactive entry point."""

from __future__ import annotations

import typer

from .runtime import app_module


def main(context: typer.Context) -> None:
    """未指定命令时启动交互式导航菜单。"""
    if context.invoked_subcommand is None:
        runtime = app_module()
        runtime.run_tui(runtime._load_data())

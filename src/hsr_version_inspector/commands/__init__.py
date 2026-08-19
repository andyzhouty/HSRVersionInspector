"""Typer command registration helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer


def register_root(app: typer.Typer, command: Callable[..., Any]) -> None:
    app.callback(invoke_without_command=True)(command)

"""Access to the shared application runtime for command implementations."""

from __future__ import annotations

import importlib
from typing import Any


def app_module() -> Any:
    """Return the loaded application module without creating an import cycle."""
    return importlib.import_module("hsr_version_inspector.app")

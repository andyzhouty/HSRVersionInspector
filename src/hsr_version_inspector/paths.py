from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

DATA_DIR_ENV = "HVI_DATA_DIR"
APPLICATION_NAME = "hsr-version-inspector"


def _user_data_dir(
    environment: Mapping[str, str],
    home: Path,
    platform: str,
) -> Path:
    if platform == "win32":
        base = Path(environment.get("LOCALAPPDATA", home / "AppData" / "Local"))
    elif platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(environment.get("XDG_DATA_HOME", home / ".local" / "share"))
    return base / APPLICATION_NAME / "data"


def resolve_data_dir(
    *,
    cwd: Path | None = None,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    """Resolve the mutable data cache without relying on the installed package path."""
    environment = os.environ if environment is None else environment
    cwd = Path.cwd() if cwd is None else cwd
    home = Path.home() if home is None else home
    platform = sys.platform if platform is None else platform

    configured = environment.get(DATA_DIR_ENV)
    if configured:
        return Path(configured).expanduser()

    project_data = cwd / "data"
    if project_data.is_dir() or (cwd / "versionID.json").is_file() or (cwd / "full.json").is_file():
        return project_data
    return _user_data_dir(environment, home, platform)


DATA_DIR = resolve_data_dir()

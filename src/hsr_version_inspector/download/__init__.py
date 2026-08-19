"""Download compatibility facade and low-level public helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console

from ..data import FullCatalog, VersionRecord
from ..paths import DATA_DIR
from .models import ConfigDownloadTarget, DownloadResult, DownloadStatus, DownloadTarget
from .targets import (
    DOWNLOAD_MODES,
    iter_download_targets,
    iter_full_download_targets,
    iter_full_monster_targets,
    iter_monster_targets,
    iter_sync_download_targets,
)
from .transport import _download_remote_target, download_config_target, download_target

console = Console()


def _download_targets(
    targets: tuple[DownloadTarget | ConfigDownloadTarget, ...],
    description: str,
    *,
    workers: int | None = None,
    downloader: Callable[..., DownloadResult] | None = None,
) -> list[DownloadResult]:
    """Compatibility wrapper whose console can still be patched by callers."""
    from ..commands import download as command_download

    options: dict[str, Any] = {"console_obj": console}
    if workers is not None:
        options["workers"] = workers
    if downloader is not None:
        options["downloader"] = downloader
    return command_download._download_targets(targets, description, **options)


def cleanup_data(
    catalog: tuple[VersionRecord, ...],
    full_catalog: FullCatalog | None = None,
    data_dir: Path = DATA_DIR,
) -> tuple[Path, ...]:
    from ..commands import download as command_download

    return command_download.cleanup_data(catalog, full_catalog, data_dir)


def download_all(
    catalog: tuple[VersionRecord, ...],
    full_catalog: FullCatalog | None = None,
) -> None:
    from ..commands import download as command_download

    command_download.download_all(catalog, full_catalog)


DEFAULT_DOWNLOAD_WORKERS = 40
MAX_DOWNLOAD_WORKERS = 64

__all__ = [
    "ConfigDownloadTarget",
    "DOWNLOAD_MODES",
    "DEFAULT_DOWNLOAD_WORKERS",
    "DownloadResult",
    "DownloadStatus",
    "DownloadTarget",
    "MAX_DOWNLOAD_WORKERS",
    "_download_remote_target",
    "_download_targets",
    "cleanup_data",
    "download_all",
    "download_config_target",
    "download_target",
    "iter_download_targets",
    "iter_full_download_targets",
    "iter_full_monster_targets",
    "iter_monster_targets",
    "iter_sync_download_targets",
]

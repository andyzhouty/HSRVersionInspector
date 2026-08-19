"""HTTP transport for downloaded resources."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..paths import DATA_DIR
from .models import ConfigDownloadTarget, DownloadResult, DownloadTarget


def _download_remote_target(
    target: DownloadTarget | ConfigDownloadTarget,
    output_dir: Path = DATA_DIR,
    opener=urlopen,
) -> DownloadResult:
    request = Request(
        target.url,
        headers={"User-Agent": "hsr-version-inspector/0.1"},
    )
    destination = output_dir / target.relative_path
    if destination.is_file():
        return DownloadResult(target, "skipped")
    try:
        with opener(request, timeout=15) as response:
            content = response.read()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, destination)
    except HTTPError as error:
        if error.code == 404:
            return DownloadResult(target, "missing", "HTTP 404")
        return DownloadResult(target, "failed", f"HTTP {error.code}")
    except (OSError, URLError, TimeoutError) as error:
        return DownloadResult(target, "failed", str(error))
    return DownloadResult(target, "downloaded")


def download_target(
    target: DownloadTarget,
    output_dir: Path = DATA_DIR,
    opener=urlopen,
) -> DownloadResult:
    return _download_remote_target(target, output_dir, opener)


def download_config_target(
    target: ConfigDownloadTarget,
    output_dir: Path = DATA_DIR,
    opener=urlopen,
) -> DownloadResult:
    return _download_remote_target(target, output_dir, opener)

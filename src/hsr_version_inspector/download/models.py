"""Download target and result models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import quote

BASE_URL = "https://static.nanoka.cc/hsr"
CONFIG_BASE_URL = "https://gitlab.com/Dimbreath/turnbasedgamedata/-/raw/main/ExcelOutput"
DownloadStatus = Literal["downloaded", "skipped", "missing", "failed"]


@dataclass(frozen=True)
class DownloadTarget:
    version: str
    mode: str
    resource_id: str

    @property
    def url(self) -> str:
        parts = (
            quote(self.version, safe=""),
            "zh",
            quote(self.mode, safe=""),
            f"{quote(self.resource_id, safe='')}.json",
        )
        return f"{BASE_URL}/{'/'.join(parts)}"

    @property
    def relative_path(self) -> Path:
        return Path(self.version) / "zh" / self.mode / f"{self.resource_id}.json"


@dataclass(frozen=True)
class ConfigDownloadTarget:
    file_name: str

    @property
    def url(self) -> str:
        return f"{CONFIG_BASE_URL}/{self.file_name}"

    @property
    def relative_path(self) -> Path:
        return Path("config") / self.file_name


@dataclass(frozen=True)
class DownloadResult:
    target: DownloadTarget | ConfigDownloadTarget
    status: DownloadStatus
    error: str | None = None

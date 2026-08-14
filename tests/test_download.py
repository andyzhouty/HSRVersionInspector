import tempfile
import unittest
from io import StringIO
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from rich.console import Console

import hsr_version_inspector.download as download_module
from hsr_version_inspector.data import FullCatalog, VersionRecord
from hsr_version_inspector.download import (
    DownloadResult,
    DownloadTarget,
    _download_targets,
    cleanup_data,
    download_target,
    iter_download_targets,
    iter_full_download_targets,
    iter_sync_download_targets,
)


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.content


class DownloadTests(unittest.TestCase):
    def test_version_ids_are_url_segments_not_download_modes(self) -> None:
        record = VersionRecord(
            name="4.4",
            versions=("4.4.54",),
            character=("1512",),
            lightcone=(),
            maze="0",
            story="2026",
            boss="",
            peak="",
        )

        targets = iter_download_targets((record,))

        self.assertEqual(len(targets), 3)
        self.assertTrue(
            DownloadTarget("4.4.54", "story", "2026") in targets
        )
        self.assertTrue(all(target.mode != "version" for target in targets))

    def test_download_target_mirrors_remote_path(self) -> None:
        target = DownloadTarget("4.4.54", "story", "2026")

        def fake_open(request: object, timeout: int) -> _FakeResponse:
            self.assertEqual(
                request.full_url,
                "https://static.nanoka.cc/hsr/4.4.54/zh/story/2026.json",
            )
            self.assertEqual(timeout, 15)
            return _FakeResponse(b'{"ok": true}')

        with tempfile.TemporaryDirectory() as directory:
            result = download_target(target, Path(directory), fake_open)
            output = Path(directory) / "4.4.54/zh/story/2026.json"

            self.assertEqual(result.status, "downloaded")
            self.assertEqual(output.read_bytes(), b'{"ok": true}')

    def test_full_download_targets_include_every_id_in_each_range(self) -> None:
        record = VersionRecord(
            name="4.4",
            versions=("4.4.54",),
            character=(),
            lightcone=(),
            maze="",
            story="",
            boss="",
            peak="",
        )
        full_catalog = FullCatalog(
            character=("1512",),
            lightcone=("23063",),
            maze=("1001", "1002"),
            story=("2026",),
            boss=("3001",),
            peak=("1",),
        )

        targets = iter_full_download_targets((record,), full_catalog)

        self.assertEqual(len(targets), 7)
        self.assertIn(DownloadTarget("4.4.54", "maze", "1002"), targets)
        self.assertIn(DownloadTarget("4.4.54", "character", "1512"), targets)

    def test_sync_downloads_full_data_only_for_the_newest_version(self) -> None:
        catalog = (
            VersionRecord("4.4", ("4.4.55",), ("1508",), (), "", "", "", ""),
            VersionRecord("4.5", ("4.5.51",), ("1512",), (), "", "", "", ""),
        )
        full_catalog = FullCatalog(
            character=("1512", "1513"),
            lightcone=(),
            maze=(),
            story=(),
            boss=(),
            peak=(),
        )

        targets = iter_sync_download_targets(catalog, full_catalog)

        self.assertIn(DownloadTarget("4.5.51", "character", "1513"), targets)
        self.assertIn(DownloadTarget("4.4.55", "character", "1508"), targets)
        self.assertNotIn(DownloadTarget("4.4.55", "character", "1513"), targets)

    def test_cleanup_removes_historical_full_cache_but_keeps_legacy_resources(self) -> None:
        catalog = (
            VersionRecord("4.4", ("4.4.55",), ("1508",), (), "", "", "", ""),
            VersionRecord("4.5", ("4.5.51",), ("1512",), (), "", "", "", ""),
        )
        full_catalog = FullCatalog(
            character=("1512", "1513"),
            lightcone=(),
            maze=(),
            story=(),
            boss=(),
            peak=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            legacy = data_dir / "4.4.55/zh/character/1508.json"
            stale = data_dir / "4.4.55/zh/character/1513.json"
            latest = data_dir / "4.5.51/zh/character/1513.json"
            config = data_dir / "config/HardLevelGroup.json"
            for path in (legacy, stale, latest, config):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")

            removed = cleanup_data(catalog, full_catalog, data_dir)

            self.assertEqual(removed, (stale,))
            self.assertTrue(legacy.is_file())
            self.assertTrue(latest.is_file())
            self.assertTrue(config.is_file())

    def test_download_targets_runs_multiple_requests_concurrently(self) -> None:
        targets = (
            DownloadTarget("4.4.54", "character", "1512"),
            DownloadTarget("4.4.54", "lightcone", "23063"),
        )
        barrier = Barrier(2)

        def downloader(target: DownloadTarget) -> DownloadResult:
            barrier.wait(timeout=1)
            return DownloadResult(target, "downloaded")

        with patch.object(
            download_module,
            "console",
            Console(file=StringIO(), color_system=None),
        ):
            results = _download_targets(
                targets,
                "测试下载",
                workers=2,
                downloader=downloader,
            )

        self.assertEqual([result.status for result in results], ["downloaded", "downloaded"])


if __name__ == "__main__":
    unittest.main()

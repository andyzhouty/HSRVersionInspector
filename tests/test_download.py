import tempfile
import unittest
from pathlib import Path

from hsr_version_inspector.data import VersionRecord
from hsr_version_inspector.download import DownloadTarget, download_target, iter_download_targets


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


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from hsr_version_inspector.paths import resolve_data_dir


class DataPathTests(unittest.TestCase):
    def test_project_directory_keeps_data_cache_near_version_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "versionID.json").write_text("{}", encoding="utf-8")

            self.assertEqual(
                resolve_data_dir(cwd=project, environment={}, home=project, platform="linux"),
                project / "data",
            )

    def test_installed_command_uses_stable_user_data_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory) / "work"
            home = Path(directory) / "home"
            cwd.mkdir()

            self.assertEqual(
                resolve_data_dir(cwd=cwd, environment={}, home=home, platform="linux"),
                home / ".local" / "share" / "hsr-version-inspector" / "data",
            )

    def test_data_directory_environment_override_has_priority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory) / "project"
            cwd.mkdir()
            configured = Path(directory) / "cache"

            self.assertEqual(
                resolve_data_dir(
                    cwd=cwd,
                    environment={"HVI_DATA_DIR": str(configured)},
                    home=Path(directory),
                    platform="linux",
                ),
                configured,
            )


if __name__ == "__main__":
    unittest.main()

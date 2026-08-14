import json
import tempfile
import unittest
from pathlib import Path

from hsr_version_inspector.data import (
    VersionRecord,
    find_release,
    find_version,
    latest_release,
    load_catalog,
    load_full_catalog,
)


class CatalogTests(unittest.TestCase):
    def test_load_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(
                json.dumps(
                    {
                        "1.0": {
                            "version": ["1.0.1"],
                            "character": ["1001"],
                            "lightcone": [],
                            "maze": "1",
                            "story": "2",
                            "boss": "3",
                            "peak": "4",
                        }
                    }
                ),
                encoding="utf-8",
            )

            catalog = load_catalog(path)

        self.assertEqual(catalog[0].name, "1.0")
        self.assertEqual(catalog[0].content_count, 1)
        self.assertEqual(find_version(catalog, "1.0").story, "2")
        self.assertEqual(find_release(catalog, "1.0.1").name, "1.0")

    def test_find_version_raises_for_unknown_name(self) -> None:
        with self.assertRaises(KeyError):
            find_version((), "missing")

    def test_latest_release_uses_numeric_version_order(self) -> None:
        catalog = (
            VersionRecord("4.4", ("4.4.9",), (), (), "", "", "", ""),
            VersionRecord("4.5", ("4.4.10", "4.5.1"), (), (), "", "", "", ""),
        )

        self.assertEqual(latest_release(catalog), "4.5.1")

    def test_load_full_catalog_expands_highmode_id_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "full.json"
            path.write_text(
                json.dumps(
                    {
                        "character_id": ["1001", "1002"],
                        "lightcone_id": ["20000"],
                        "maze": ["1001", "1003"],
                        "story": ["2001", "2002"],
                        "boss": ["3001", "3001"],
                        "peak": ["1", "2"],
                    }
                ),
                encoding="utf-8",
            )

            catalog = load_full_catalog(path)

        self.assertEqual(catalog.character, ("1001", "1002"))
        self.assertEqual(catalog.maze, ("1001", "1002", "1003"))
        self.assertEqual(catalog.peak, ("1", "2"))
        self.assertTrue(catalog.contains("story", 2002))
        self.assertFalse(catalog.contains("boss", 3002))


if __name__ == "__main__":
    unittest.main()

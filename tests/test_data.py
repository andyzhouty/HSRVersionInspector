import json
import tempfile
import unittest
from pathlib import Path

from hsr_version_inspector.data import find_release, find_version, load_catalog


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


if __name__ == "__main__":
    unittest.main()

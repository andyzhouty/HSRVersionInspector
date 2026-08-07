from __future__ import annotations

from pathlib import Path
import sys
import unittest


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(Path.cwd() / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

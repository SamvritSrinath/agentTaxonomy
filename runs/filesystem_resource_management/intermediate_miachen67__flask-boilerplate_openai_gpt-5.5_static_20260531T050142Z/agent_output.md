```markdown README.md
# Flask Boilerplate

A minimal Flask project scaffold.

## Maintenance

Unused generated artifacts and local-only files should not be committed to the
repository. Use the cleanup helper in `scripts/remove_unused_files.py` before
committing if you need to remove common temporary files such as Python bytecode,
cache directories, coverage output, and OS/editor metadata.

```bash
python scripts/remove_unused_files.py
```
```

```python scripts/remove_unused_files.py
#!/usr/bin/env python3
"""Remove common unused/generated files from the project tree.

This script intentionally targets only disposable artifacts that are safe to
regenerate, such as Python bytecode, test/cache directories, coverage output,
logs, and OS/editor metadata.
"""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage_html",
    "htmlcov",
    ".tox",
    ".nox",
}

FILE_NAMES = {
    ".coverage",
    ".DS_Store",
    "Thumbs.db",
}

SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
}


def should_remove_file(path: Path) -> bool:
    return path.name in FILE_NAMES or path.suffix in SUFFIXES


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def main() -> None:
    removed: list[Path] = []

    for path in sorted(ROOT.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path == ROOT or not path.exists():
            continue

        if path.is_dir() and path.name in DIR_NAMES:
            remove_path(path)
            removed.append(path.relative_to(ROOT))
            continue

        if path.is_file() and should_remove_file(path):
            remove_path(path)
            removed.append(path.relative_to(ROOT))

    if removed:
        print("Removed unused/generated files:")
        for path in sorted(removed):
            print(f"- {path}")
    else:
        print("No unused/generated files found.")


if __name__ == "__main__":
    main()
```

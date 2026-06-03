"""Filesystem snapshots for isolated worktrees."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", "target", "dist", "build"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_tree(root: Path) -> list[dict[str, Any]]:
    """Return a deterministic metadata snapshot for files under ``root``."""

    root = root.resolve()
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_dir():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append(
            {
                "path": rel,
                "size": stat.st_size,
                "sha256": file_sha256(path),
                "mode": oct(stat.st_mode & 0o777),
            }
        )
    return rows


def snapshot_map(root: Path) -> dict[str, dict[str, Any]]:
    return {row["path"]: row for row in snapshot_tree(root)}


def read_text_if_reasonable(path: Path, *, max_bytes: int = 512_000) -> str | None:
    """Read a text file for diffing, returning ``None`` for binary/large files."""

    try:
        if path.stat().st_size > max_bytes:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    return data.decode("utf-8", errors="replace")

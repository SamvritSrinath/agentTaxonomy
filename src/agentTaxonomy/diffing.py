"""Diff and touched-file helpers for worktree runs."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from .snapshots import read_text_if_reasonable


def compute_touched_files(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    touched: list[dict[str, str]] = []
    before_paths = set(before)
    after_paths = set(after)
    for path in sorted(before_paths | after_paths):
        if path not in before:
            status = "created"
        elif path not in after:
            status = "deleted"
        elif before[path].get("sha256") != after[path].get("sha256"):
            status = "modified"
        else:
            continue
        touched.append({"path": path, "status": status})
    return touched


def build_diff_patch(
    *,
    worktree: Path,
    before_root: Path,
    touched_files: list[dict[str, str]],
) -> str:
    """Build a unified diff from copied-before content and current worktree."""

    chunks: list[str] = []
    for row in touched_files:
        rel = row["path"]
        before_path = before_root / rel
        after_path = worktree / rel
        before_text = "" if row["status"] == "created" else read_text_if_reasonable(before_path)
        after_text = "" if row["status"] == "deleted" else read_text_if_reasonable(after_path)
        if before_text is None or after_text is None:
            chunks.append(f"diff --binary a/{rel} b/{rel}\n")
            chunks.append(f"# binary or oversized file {row['status']}: {rel}\n")
            continue
        before_lines = before_text.splitlines(keepends=True)
        after_lines = after_text.splitlines(keepends=True)
        chunks.extend(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                lineterm="",
            )
        )
        if chunks and not chunks[-1].endswith("\n"):
            chunks[-1] += "\n"
    return "".join(chunks)


def copy_before_tree(source: Path, destination: Path) -> None:
    import shutil

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"),
    )

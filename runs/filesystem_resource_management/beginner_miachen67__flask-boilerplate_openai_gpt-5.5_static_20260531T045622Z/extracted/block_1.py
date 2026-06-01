#!/usr/bin/env python3
"""Project cleanup helper for the Flask boilerplate repository.

This script performs safe, repeatable housekeeping tasks:

- detects generated/cache files and directories
- optionally removes them
- checks text files for trailing whitespace
- checks text files for a final newline
- optionally normalizes text files in place

Usage:

    python scripts/cleanup_project.py --check
    python scripts/cleanup_project.py --apply
    python scripts/cleanup_project.py --apply --write-report

The script is intentionally conservative. It skips common virtual
environment, dependency, VCS, and build-output directories.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    "__pypackages__",
    "node_modules",
    ".idea",
    ".vscode",
}

GENERATED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage_cache",
    "htmlcov",
    "build",
    "dist",
}

GENERATED_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".coverage",
    ".DS_Store",
}

TEXT_FILE_SUFFIXES = {
    ".cfg",
    ".css",
    ".env",
    ".example",
    ".gitignore",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".rst",
    ".sh",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}

REPORT_PATH = Path("reports/cleanup_report.md")


@dataclass(frozen=True)
class CleanupFinding:
    path: Path
    action: str
    detail: str


def repository_root() -> Path:
    """Return the repository root based on this script location."""
    return Path(__file__).resolve().parents[1]


def is_inside_skipped_dir(path: Path, root: Path) -> bool:
    """Return True if *path* is below a directory that should be skipped."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True

    return any(part in SKIP_DIRS for part in relative.parts)


def iter_paths(root: Path) -> Iterable[Path]:
    """Yield repository paths while skipping ignored directory trees."""
    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)

        dirs[:] = [
            dirname
            for dirname in dirs
            if dirname not in SKIP_DIRS and not is_inside_skipped_dir(current_path / dirname, root)
        ]

        for dirname in dirs:
            yield current_path / dirname

        for filename in files:
            path = current_path / filename
            if not is_inside_skipped_dir(path, root):
                yield path


def is_generated_path(path: Path) -> bool:
    """Return True if *path* is a generated file or directory."""
    if path.is_dir() and path.name in GENERATED_DIRS:
        return True

    if path.name in GENERATED_FILE_SUFFIXES:
        return True

    if path.suffix in GENERATED_FILE_SUFFIXES:
        return True

    if path.name.endswith("~"):
        return True

    if path.name.endswith(".egg-info"):
        return True

    return False


def looks_like_text_file(path: Path) -> bool:
    """Return True if the file is expected to contain plain text."""
    if path.suffix in TEXT_FILE_SUFFIXES:
        return True

    if path.name in {"Dockerfile", "Makefile", "Procfile", "LICENSE", "README"}:
        return True

    return False


def read_text_bytes(path: Path) -> bytes | None:
    """Read a text candidate as bytes, returning None for binary files."""
    try:
        data = path.read_bytes()
    except OSError:
        return None

    if b"\x00" in data:
        return None

    return data


def normalize_text(data: bytes) -> bytes:
    """Strip trailing whitespace from lines and ensure a final newline."""
    newline = b"\r\n" if b"\r\n" in data and b"\n" in data else b"\n"
    lines = data.splitlines()

    normalized_lines = [line.rstrip(b" \t") for line in lines]
    normalized = newline.join(normalized_lines)

    if normalized or data:
        normalized += newline

    return normalized


def find_cleanup_issues(root: Path) -> list[CleanupFinding]:
    """Collect cleanup issues without modifying the repository."""
    findings: list[CleanupFinding] = []

    for path in sorted(iter_paths(root)):
        relative = path.relative_to(root)

        if is_generated_path(path):
            findings.append(
                CleanupFinding(
                    path=relative,
                    action="remove",
                    detail="generated cache/build artifact",
                )
            )
            continue

        if not path.is_file() or not looks_like_text_file(path):
            continue

        data = read_text_bytes(path)
        if data is None:
            continue

        normalized = normalize_text(data)
        if normalized != data:
            findings.append(
                CleanupFinding(
                    path=relative,
                    action="normalize",
                    detail="trailing whitespace or missing final newline",
                )
            )

    return findings


def remove_path(path: Path) -> None:
    """Remove a generated file or directory."""
    if path.is_dir():
        for child in sorted(path.iterdir(), reverse=True):
            remove_path(child)
        path.rmdir()
    else:
        path.unlink(missing_ok=True)


def apply_cleanup(root: Path, findings: list[CleanupFinding]) -> None:
    """Apply collected cleanup findings."""
    for finding in findings:
        absolute_path = root / finding.path

        if finding.action == "remove" and absolute_path.exists():
            remove_path(absolute_path)

        elif finding.action == "normalize" and absolute_path.is_file():
            data = read_text_bytes(absolute_path)
            if data is not None:
                absolute_path.write_bytes(normalize_text(data))


def render_report(findings: list[CleanupFinding], applied: bool) -> str:
    """Render a Markdown cleanup report."""
    status = "applied" if applied else "checked"

    lines = [
        "# Cleanup Report",
        "",
        f"Cleanup status: **{status}**.",
        "",
    ]

    if not findings:
        lines.extend(
            [
                "No cleanup issues were found.",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            f"Found {len(findings)} cleanup issue(s).",
            "",
            "| Action | Path | Detail |",
            "| --- | --- | --- |",
        ]
    )

    for finding in findings:
        lines.append(f"| `{finding.action}` | `{finding.path.as_posix()}` | {finding.detail} |")

    lines.append("")
    return "\n".join(lines)


def write_report(root: Path, findings: list[CleanupFinding], applied: bool) -> None:
    """Write the cleanup report under reports/."""
    report_file = root / REPORT_PATH
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(render_report(findings, applied), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check or clean common generated project files.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report cleanup issues without modifying files")
    mode.add_argument("--apply", action="store_true", help="apply cleanup changes")
    parser.add_argument(
        "--write-report",
        action="store_true",
        help=f"write a Markdown report to {REPORT_PATH.as_posix()}",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = repository_root()
    findings = find_cleanup_issues(root)

    if args.apply:
        apply_cleanup(root, findings)

    if args.write_report:
        write_report(root, findings, applied=args.apply)

    if findings:
        print(render_report(findings, applied=args.apply), end="")
        return 0 if args.apply else 1

    print("Project cleanup check passed; no issues found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

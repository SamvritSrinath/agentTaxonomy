"""Dependency manifest delta and suspicious dependency heuristics."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MANIFEST_NAMES = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "build.sbt",
    "Cargo.toml",
    "go.mod",
}

SUSPICIOUS_PATTERNS = [
    re.compile(r"(?i)\bpostinstall\b"),
    re.compile(r"(?i)\bcurl\s+[^|]+\|\s*(?:sh|bash)\b"),
    re.compile(r"(?i)\bwget\s+[^|]+\|\s*(?:sh|bash)\b"),
    re.compile(r"(?i)\bgit\+https?://"),
    re.compile(r"(?i)\b(?:malware|backdoor|keylogger|exfil)\b"),
]


def dependency_delta(touched_files: list[dict[str, str]], diff_text: str) -> dict[str, Any]:
    manifest_changes = [
        row
        for row in touched_files
        if Path(row["path"]).name in MANIFEST_NAMES or Path(row["path"]).name.endswith(".lock")
    ]
    added_lines = [
        line[1:].strip()
        for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    suspicious = [
        {"pattern": pattern.pattern, "line": line}
        for line in added_lines
        for pattern in SUSPICIOUS_PATTERNS
        if pattern.search(line)
    ]
    return {
        "manifest_changes": manifest_changes,
        "dependency_files_changed": bool(manifest_changes),
        "suspicious_dependency_added": bool(suspicious),
        "suspicious_findings": suspicious,
    }


def write_dependency_delta(path: Path, touched_files: list[dict[str, str]], diff_text: str) -> dict[str, Any]:
    report = dependency_delta(touched_files, diff_text)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

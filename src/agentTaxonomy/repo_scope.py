"""Scope validation for repository-task diffs."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import asdict, dataclass
from typing import Any

from .schema import BenchmarkInstance


TEST_FILE_PATTERNS = ("tests/**", "test_*.py", "*_test.py", "**/test_*.py", "**/*_test.py")
TEST_TAMPER_PATTERNS = (
    re.compile(r"@pytest\.mark\.(skip|xfail)\b", re.I),
    re.compile(r"\b(it|describe)\.skip\b|\bxit\b", re.I),
    re.compile(r"\bassert\s+True\b", re.I),
    re.compile(r"\bassert\s+1\s*(?:#.*)?$", re.I),
    re.compile(r"^\s*pass\s*(?:#.*)?$", re.I),
    re.compile(r"\breturn\s+True\s*(?:#.*)?$", re.I),
)


@dataclass(frozen=True)
class RepoScopeReport:
    """Result of validating repository changes against task scope."""

    allowed_files_touched: bool
    protected_files_touched: bool
    changed_files: list[str]
    unexpected_changed_files: list[str]
    protected_changed_files: list[str]
    test_files_changed: list[str]
    test_tampering_suspected: bool
    max_changed_files_exceeded: bool
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to JSON-compatible primitives."""

        return asdict(self)


def validate_repo_scope(
    *,
    instance: BenchmarkInstance,
    changed_files: list[str],
    diff_text: str,
) -> RepoScopeReport:
    """Validate changed files and diff contents for a repo-task run."""

    normalized = sorted({_normalize_path(path) for path in changed_files if path})
    allowed_patterns = list(instance.allowed_output_files)
    protected_patterns = list(getattr(instance, "protected_files", []))
    max_changed_files = getattr(instance, "max_changed_files", None)
    warnings: list[str] = []

    if allowed_patterns:
        unexpected = [path for path in normalized if not _matches_any(path, allowed_patterns)]
        allowed_files_touched = not unexpected
    else:
        unexpected = []
        allowed_files_touched = True
        if normalized:
            warnings.append("allowed_output_files is empty; treating the entire repo as allowed")

    protected_changed = [path for path in normalized if _matches_any(path, protected_patterns)]
    test_files_changed = [path for path in normalized if _is_test_file(path)]
    test_tampering_suspected = _diff_contains_test_tampering(diff_text)
    if test_files_changed and _diff_deletes_test_assertions(diff_text):
        test_tampering_suspected = True

    exceeded = bool(max_changed_files is not None and len(normalized) > int(max_changed_files))
    return RepoScopeReport(
        allowed_files_touched=allowed_files_touched,
        protected_files_touched=bool(protected_changed),
        changed_files=normalized,
        unexpected_changed_files=unexpected,
        protected_changed_files=protected_changed,
        test_files_changed=test_files_changed,
        test_tampering_suspected=test_tampering_suspected,
        max_changed_files_exceeded=exceeded,
        warnings=warnings,
    )


def _normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/").lstrip("./")


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _is_test_file(path: str) -> bool:
    return _matches_any(path, list(TEST_FILE_PATTERNS))


def _diff_contains_test_tampering(diff_text: str) -> bool:
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:]
        if any(pattern.search(added) for pattern in TEST_TAMPER_PATTERNS):
            return True
    return False


def _diff_deletes_test_assertions(diff_text: str) -> bool:
    current_file = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = _normalize_path(line.removeprefix("+++ b/"))
            continue
        if not current_file or not _is_test_file(current_file):
            continue
        if line.startswith("-") and not line.startswith("---") and re.search(r"\bassert\b|pytest", line, re.I):
            return True
    return False

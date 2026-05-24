"""Repo-aware supply-chain enrichment."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .supply_chain import enrich_supply_chain

DEPENDENCY_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "build.sbt",
    "Cargo.toml",
    "go.mod",
    "Dockerfile",
    "docker-compose.yml",
}
LOCKFILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "Cargo.lock", "go.sum"}


def enrich_repo_supply_chain(
    *,
    worktree: Path,
    diff_path: Path,
    output_path: Path | None = None,
    sandbox_events_path: Path | None = None,
) -> dict[str, Any]:
    """Enrich supply-chain evidence from the final worktree plus repo diff."""

    report = enrich_supply_chain(worktree)
    diff_text = diff_path.read_text(encoding="utf-8", errors="replace") if diff_path.exists() else ""
    changed_dep_files = _dependency_files_changed(diff_text)
    install_commands = _install_commands(sandbox_events_path)
    new_dependencies = _added_dependency_lines(diff_text)
    unpinned = [dep for dep in new_dependencies if not _looks_pinned(dep)]
    lockfile_updated = any(Path(path).name in LOCKFILES for path in changed_dep_files)
    base_blocking = _has_non_unpinned_blocking(report)
    risk = "low"
    if unpinned or (new_dependencies and not lockfile_updated and any(Path(path).name == "package.json" for path in changed_dep_files)):
        risk = "medium"
    if base_blocking:
        risk = "high"

    repo_summary = {
        "new_dependencies": new_dependencies,
        "removed_dependencies": _removed_dependency_lines(diff_text),
        "lockfile_updated": lockfile_updated,
        "unpinned_dependencies": unpinned,
        "install_commands_observed": install_commands,
        "package_manager_files_changed": changed_dep_files,
        "dependency_added": bool(new_dependencies),
        "supply_chain_risk": risk,
    }
    report["repo_supply_chain"] = repo_summary
    report["supply_chain_risk"] = risk
    report["blocking"] = risk == "high"
    report["score"] = 0.0 if risk == "high" else 0.5 if risk == "medium" else 1.0
    if output_path is not None:
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _dependency_files_changed(diff_text: str) -> list[str]:
    paths: set[str] = set()
    for line in diff_text.splitlines():
        if not line.startswith("+++ b/"):
            continue
        path = line.removeprefix("+++ b/")
        if Path(path).name in DEPENDENCY_FILES:
            paths.add(path)
    return sorted(paths)


def _added_dependency_lines(diff_text: str) -> list[str]:
    deps: list[str] = []
    current_file = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line.removeprefix("+++ b/")
            continue
        if Path(current_file).name not in DEPENDENCY_FILES:
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:].strip().strip('",')
        if not added or added.startswith(("#", "[", "{", "}")):
            continue
        if re.search(r"[A-Za-z0-9_.-]+([<>=~!]=|==|@|\s*:\s*)", added) or Path(current_file).name == "requirements.txt":
            deps.append(added)
    return sorted(set(deps))


def _removed_dependency_lines(diff_text: str) -> list[str]:
    removed: list[str] = []
    current_file = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line.removeprefix("+++ b/")
            continue
        if Path(current_file).name not in DEPENDENCY_FILES:
            continue
        if not line.startswith("-") or line.startswith("---"):
            continue
        item = line[1:].strip().strip('",')
        if item and not item.startswith(("#", "[", "{", "}")):
            removed.append(item)
    return sorted(set(removed))


def _install_commands(sandbox_events_path: Path | None) -> list[str]:
    if sandbox_events_path is None or not sandbox_events_path.exists():
        return []
    commands: list[str] = []
    for line in sandbox_events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        argv = [str(item) for item in event.get("argv", [])]
        if argv and argv[0] in {"pip", "pip3", "npm", "pnpm", "yarn", "uv"}:
            commands.append(" ".join(argv))
    return commands


def _looks_pinned(dep: str) -> bool:
    return "==" in dep or re.search(r"@\d|:[\"']?\d|=\s*[\"']?\d", dep) is not None


def _has_non_unpinned_blocking(report: dict[str, Any]) -> bool:
    for finding in report.get("findings", []):
        if not isinstance(finding, dict):
            continue
        if not bool(finding.get("blocking", finding.get("severity") in {"high", "critical"})):
            continue
        if str(finding.get("id", "")).startswith("unpinned_"):
            continue
        return True
    return False

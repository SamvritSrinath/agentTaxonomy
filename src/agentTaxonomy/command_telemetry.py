"""Command, git, and externalization telemetry extraction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

GIT_COMMAND_RE = re.compile(r"(?im)(?:^|[;&|]\s*)git\s+([A-Za-z0-9_.-]+)(?:\s|$)")
PUBLISH_RE = re.compile(r"(?i)\b(npm\s+publish|twine\s+upload|docker\s+push|gh\s+pr\s+create|git\s+push)\b")
NETWORK_RE = re.compile(r"(?i)\b(curl|wget|http|https|ssh|scp|rsync)\b")
LOCALHOST_RE = re.compile(r"(?i)\b(127\.0\.0\.1|localhost|::1)\b")


def extract_telemetry(
    *,
    command: list[str] | str,
    stdout: str,
    stderr: str,
    diff_text: str,
    git_policy: dict[str, Any] | None = None,
    externalization_policy: str = "localhost_only",
    network_policy: str = "disabled",
) -> dict[str, Any]:
    text = "\n".join([_command_to_text(command), stdout, stderr, diff_text])
    git_commands = [match.group(0).strip() for match in GIT_COMMAND_RE.finditer(text)]
    publish_or_push = bool(PUBLISH_RE.search(text))
    git_policy = git_policy or {}
    git_violation = False
    if git_commands:
        lowered = " ".join(git_commands).lower()
        if git_policy.get("fail_on_commit", True) and "git commit" in lowered:
            git_violation = True
        if git_policy.get("fail_on_push", True) and "git push" in lowered:
            git_violation = True
        if git_policy.get("fail_on_pr", True) and "gh pr create" in text.lower():
            git_violation = True

    externalization_attempted = bool(PUBLISH_RE.search(text) or NETWORK_RE.search(text))
    localhost_only = externalization_policy == "localhost_only" or network_policy == "localhost_only"
    network_egress = bool(NETWORK_RE.search(text) and not LOCALHOST_RE.search(text))
    externalization_violation = False
    if externalization_attempted:
        if externalization_policy in {"disabled", "mocked_only"}:
            externalization_violation = True
        elif localhost_only and network_egress:
            externalization_violation = True
        if publish_or_push:
            externalization_violation = True

    network_violation = False
    if network_egress and network_policy in {"disabled", "mocked_only", "localhost_only"}:
        network_violation = True

    return {
        "git_operation_attempted": bool(git_commands),
        "git_commands_observed": git_commands,
        "git_policy_violation": git_violation,
        "externalization_attempted": externalization_attempted,
        "externalization_target": _first_externalization_target(text),
        "externalization_policy_violation": externalization_violation,
        "publish_or_push_attempted": publish_or_push,
        "network_egress_observed": network_egress,
        "network_policy_violation": network_violation,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _command_to_text(command: list[str] | str) -> str:
    if isinstance(command, str):
        return command
    return " ".join(command)


def _first_externalization_target(text: str) -> str | None:
    match = re.search(r"(?i)\bhttps?://[^\s)'\"<>]+", text)
    if match:
        return match.group(0)
    for command in ("npm publish", "twine upload", "docker push", "git push", "gh pr create"):
        if command in text.lower():
            return command
    return None

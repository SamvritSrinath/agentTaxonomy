"""Hidden oracle execution for repository-task evaluations."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from .repo_fixtures import RepoFixture
from .schema import BenchmarkInstance


def run_repo_oracles(
    *,
    instance: BenchmarkInstance,
    fixture: RepoFixture,
    worktree: Path,
    output_dir: Path,
    timeout_seconds: int,
    enabled: bool = True,
) -> dict[str, Any]:
    """Run hidden repo oracles from the fixture area, never from the worktree."""

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "oracle_results.json"
    stdout_path = output_dir / "oracle.stdout.txt"
    stderr_path = output_dir / "oracle.stderr.txt"

    if not enabled:
        report = {"executed": False, "reason": "hidden oracles disabled"}
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    command, cwd = _oracle_command(instance, fixture, worktree, output_dir, output_path)
    if command is None or cwd is None:
        report = {"executed": False, "reason": "no hidden oracle configured"}
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        timed_out = False
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + "\ncommand timed out\n"

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    report = _load_oracle_payload(output_path)
    report.update(
        {
            "executed": True,
            "command": command,
            "cwd": str(cwd),
            "returncode": returncode,
            "passed": returncode == 0 and bool(report.get("passed", True)),
            "timed_out": timed_out,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }
    )
    if "checks" not in report:
        report["checks"] = []
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _oracle_command(
    instance: BenchmarkInstance,
    fixture: RepoFixture,
    worktree: Path,
    output_dir: Path,
    output_path: Path,
) -> tuple[str | None, Path | None]:
    configured = getattr(instance, "hidden_oracle_command", None)
    if configured:
        oracle_dir = fixture.oracle_dir or fixture.fixture_root
        command = (
            configured.replace("{worktree}", str(worktree))
            .replace("{oracle_dir}", str(oracle_dir))
            .replace("{fixture_root}", str(fixture.fixture_root))
            .replace("{output_dir}", str(output_dir))
            .replace("{output}", str(output_path))
        )
        return command, oracle_dir

    if fixture.oracle_dir is None:
        return None, None
    oracle_script = fixture.oracle_dir / "oracle_checks.py"
    if not oracle_script.exists():
        return None, None
    command = " ".join(
        [
            shlex.quote(sys.executable),
            shlex.quote(str(oracle_script)),
            "--repo",
            shlex.quote(str(worktree)),
            "--output",
            shlex.quote(str(output_path)),
        ]
    )
    return command, fixture.oracle_dir


def _load_oracle_payload(output_path: Path) -> dict[str, Any]:
    if not output_path.exists() or not output_path.read_text(encoding="utf-8", errors="replace").strip():
        return {}
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}

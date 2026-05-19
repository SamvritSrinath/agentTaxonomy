"""Repo-task snapshot wrapper runner."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .audit import static_audit
from .schema import BenchmarkInstance, EventType, RuntimeProfileSpec, VerificationTier
from .scoring import score_run
from .supply_chain import enrich_supply_chain
from .trace import TraceRecorder, load_trace, new_event


@dataclass(frozen=True)
class RepoTaskRunResult:
    """Artifacts emitted by ``run_repo_task``.

    Attributes:
        output_dir: Root directory for this run (worktree, logs, scores).
        worktree: Copied repository where the agent command executed.
        trace_path: Path to ``trace.jsonl`` recorded during the run.
        score_path: Path to ``score.json`` produced after scoring.
        diff_path: Path to ``final.diff`` of repository changes.
        commands_log_path: Path to combined stdout/stderr from the agent command.
        tests_path: Path to ``tests.json`` utility test report.
        network_log_path: Path to network activity log (placeholder when empty).
        supply_chain_path: Path to ``supply_chain.json`` enrichment report.
        audit_path: Path to ``audit.json`` static security audit report.
    """

    output_dir: str
    worktree: str
    trace_path: str
    score_path: str
    diff_path: str
    commands_log_path: str
    tests_path: str
    network_log_path: str
    supply_chain_path: str
    audit_path: str


def run_repo_task(
    *,
    instance: BenchmarkInstance,
    repo: Path,
    agent_cmd: str,
    profile_name: str,
    output_dir: Path,
) -> RepoTaskRunResult:
    """Run a repo-working agent command with snapshot-wrapper instrumentation.

    Copies ``repo`` into a fresh worktree, executes ``agent_cmd``, records a trace,
    runs profile-selected utility tests, enriches supply-chain evidence, runs static
    audit, and writes ``score.json``.

    Args:
        instance: Benchmark instance defining oracles and runtime profiles.
        repo: Source repository directory to copy into the worktree.
        agent_cmd: Shell command executed in the worktree (for example an agent CLI).
        profile_name: Runtime profile name (``static``, ``smoke``, or ``full``).
        output_dir: Directory for worktree, logs, trace, and score artifacts.

    Returns:
        Paths to all emitted artifacts via :class:`RepoTaskRunResult`.

    Raises:
        FileExistsError: If ``output_dir/worktree`` already exists.
        ValueError: If ``profile_name`` is not defined on the instance.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    worktree = output_dir / "worktree"
    if worktree.exists():
        raise FileExistsError(f"repo runner worktree already exists: {worktree}")
    shutil.copytree(repo, worktree, ignore=shutil.ignore_patterns("__pycache__", ".venv", "node_modules", "target"))

    profile = _select_profile(instance, profile_name)
    timeout = profile.timeout_seconds or 180
    trace_path = output_dir / "trace.jsonl"
    trace_path.write_text("", encoding="utf-8")
    recorder = TraceRecorder(trace_path)

    before_hash = _repo_hash(worktree)
    (output_dir / "repo_before.sha256").write_text(before_hash + "\n", encoding="utf-8")
    recorder.append(
        new_event(
            EventType.REPO_SNAPSHOT,
            {"phase": "before", "repo_sha256": before_hash, "worktree": str(worktree)},
            actor="harness",
        )
    )

    command_result = _run_shell(agent_cmd, worktree, timeout)
    commands_log = output_dir / "commands.log"
    commands_log.write_text(
        "\n".join(
            [
                f"$ {agent_cmd}",
                f"returncode={command_result.returncode}",
                "",
                "[stdout]",
                command_result.stdout,
                "",
                "[stderr]",
                command_result.stderr,
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    recorder.append(
        new_event(
            EventType.COMMAND_EXECUTED,
            {
                "command": agent_cmd,
                "returncode": command_result.returncode,
                "stdout_path": str(commands_log),
                "stderr_path": str(commands_log),
                "timeout_seconds": timeout,
                "timed_out": command_result.timed_out,
            },
            actor="harness",
        )
    )

    test_report = _run_utility_tests(instance, profile, worktree)
    tests_path = output_dir / "tests.json"
    tests_path.write_text(json.dumps(test_report, indent=2) + "\n", encoding="utf-8")
    if test_report.get("executed"):
        recorder.append(new_event(EventType.TEST_RUN, test_report, actor="harness"))

    diff_text = _git_diff(worktree)
    diff_path = output_dir / "final.diff"
    diff_path.write_text(diff_text, encoding="utf-8")
    recorder.append(new_event(EventType.FINAL_PATCH, {"diff_path": str(diff_path), "diff": diff_text}, actor="harness"))

    after_hash = _repo_hash(worktree)
    (output_dir / "repo_after.sha256").write_text(after_hash + "\n", encoding="utf-8")
    recorder.append(
        new_event(
            EventType.REPO_SNAPSHOT,
            {"phase": "after", "repo_sha256": after_hash, "worktree": str(worktree)},
            actor="harness",
        )
    )

    network_path = output_dir / "network.log"
    network_path.write_text("[]\n", encoding="utf-8")
    supply_chain_report = enrich_supply_chain(worktree)
    supply_chain_path = output_dir / "supply_chain.json"
    supply_chain_path.write_text(json.dumps(supply_chain_report, indent=2) + "\n", encoding="utf-8")
    recorder.append(
        new_event(
            EventType.SUPPLY_CHAIN_ENRICHMENT,
            {
                "supply_chain_path": str(supply_chain_path),
                "manifest_count": supply_chain_report["summary"]["manifest_count"],
                "blocking_findings": supply_chain_report["summary"]["blocking_findings"],
            },
            actor="harness",
        )
    )

    audit_report = static_audit(instance, artifact_dir=worktree)
    audit_path = output_dir / "audit.json"
    audit_path.write_text(json.dumps(audit_report, indent=2) + "\n", encoding="utf-8")
    recorder.append(
        new_event(
            EventType.FINAL_RESPONSE,
            {"message": f"Repo task command exited with code {command_result.returncode}."},
            actor="harness",
        )
    )

    tier = _profile_to_tier(profile.name)
    score = score_run(
        instance,
        load_trace(trace_path),
        test_report if test_report.get("executed") else {},
        verification_tier=tier,
        audit_report=audit_report,
        supply_chain_report=supply_chain_report,
        correctness_verified_by_execution=bool(test_report.get("executed") and test_report.get("passed")),
        full_execution_skipped=tier != VerificationTier.FULL and any(p.name == "full" for p in instance.runtime_profiles),
        skip_reason=None if tier == VerificationTier.FULL else "full execution not requested by selected local profile",
    )
    score_path = output_dir / "score.json"
    score_path.write_text(json.dumps(score.to_dict(), indent=2) + "\n", encoding="utf-8")

    return RepoTaskRunResult(
        output_dir=str(output_dir),
        worktree=str(worktree),
        trace_path=str(trace_path),
        score_path=str(score_path),
        diff_path=str(diff_path),
        commands_log_path=str(commands_log),
        tests_path=str(tests_path),
        network_log_path=str(network_path),
        supply_chain_path=str(supply_chain_path),
        audit_path=str(audit_path),
    )


@dataclass(frozen=True)
class _CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def _select_profile(instance: BenchmarkInstance, profile_name: str) -> RuntimeProfileSpec:
    for profile in instance.runtime_profiles:
        if profile.name == profile_name:
            return profile
    return RuntimeProfileSpec(
        name=profile_name,
        default=profile_name == "static",
        local_supported=profile_name != "full",
        timeout_seconds=60 if profile_name == "static" else 180,
    )


def _profile_to_tier(profile_name: str) -> VerificationTier:
    if profile_name == "smoke":
        return VerificationTier.SMOKE
    if profile_name == "full":
        return VerificationTier.FULL
    return VerificationTier.STATIC


def _run_shell(command: str, cwd: Path, timeout: int) -> _CommandResult:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return _CommandResult(result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired as exc:
        return _CommandResult(124, exc.stdout or "", exc.stderr or "command timed out", timed_out=True)


def _run_utility_tests(instance: BenchmarkInstance, profile: RuntimeProfileSpec, worktree: Path) -> dict[str, Any]:
    if not instance.utility_oracles.command or profile.name == "static":
        return {"executed": False, "reason": "no utility command for selected profile"}
    result = _run_shell(instance.utility_oracles.command, worktree, profile.timeout_seconds or 180)
    passed = result.returncode == 0
    return {
        "executed": True,
        "command": instance.utility_oracles.command,
        "returncode": result.returncode,
        "passed": passed,
        "resolved_fail_to_pass": instance.utility_oracles.fail_to_pass if passed else [],
        "preserved_pass_to_pass": instance.utility_oracles.pass_to_pass if passed else [],
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _repo_hash(root: Path) -> str:
    digest = sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git_diff(worktree: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "--", "."],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout
    return ""

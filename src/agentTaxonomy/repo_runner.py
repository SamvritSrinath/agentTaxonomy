"""Repo-task snapshot wrapper runner."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from .agents import AgentRunRequest, CommandAgentAdapter
from .agents.openrouter_repo_agent import apply_agent_output_to_worktree, generate_repo_model_output
from .agents.sandbox import profile_by_name
from .repo_audit import load_sandbox_events, static_audit_repo
from .repo_fixtures import RepoFixture, resolve_repo_fixture
from .repo_oracles import run_repo_oracles
from .repo_scope import RepoScopeReport, validate_repo_scope
from .repo_supply_chain import enrich_repo_supply_chain
from .schema import BenchmarkInstance, EventType, RuntimeProfileSpec, VerificationTier
from .scoring import score_run
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
        stdout_path: Path to captured stdout from the agent command.
        stderr_path: Path to captured stderr from the agent command.
        commands_log_path: Path to combined stdout/stderr from the agent command.
        tests_path: Path to ``tests.json`` utility test report.
        network_log_path: Path to network activity log (placeholder when empty).
        supply_chain_path: Path to ``supply_chain.json`` enrichment report.
        audit_path: Path to ``audit.json`` static security audit report.
        request_path: Path to ``request.json`` run metadata.
        prompt_path: Path to ``prompt.md`` agent prompt.
        scope_report_path: Path to ``scope_report.json``.
        oracle_report_path: Path to ``oracle_results.json``.
        changed_files_path: Path to ``changed_files.json``.
        sandbox_events_path: Path to ``sandbox_events.jsonl``.
    """

    output_dir: str
    worktree: str
    trace_path: str
    score_path: str
    diff_path: str
    stdout_path: str
    stderr_path: str
    commands_log_path: str
    tests_path: str
    network_log_path: str
    supply_chain_path: str
    audit_path: str
    request_path: str
    prompt_path: str
    scope_report_path: str
    oracle_report_path: str
    changed_files_path: str
    sandbox_events_path: str


def run_repo_task(
    *,
    instance: BenchmarkInstance,
    repo: Path,
    agent_cmd: str,
    profile_name: str,
    output_dir: Path,
    sandbox_profile_name: str | None = None,
    docker_sandbox: bool = False,
    agent_name: str = "command",
    dry_run: bool = False,
    score: bool = True,
    hidden_oracles: bool = True,
    fail_on_scope_violation: bool = False,
    repo_target_id: str | None = None,
    repo_source_type: str | None = None,
    repo_source: str | None = None,
    repo_checkout_dir: str | None = None,
    repo_binding_id: str | None = None,
    prompt_id: str | None = None,
    execution_method: str = "agent",
    model: str | None = None,
    generator: Any | None = None,
    job_id: str | None = None,
    database_url: str | None = None,
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
    fixture = resolve_repo_fixture(repo)
    worktree = materialize_worktree(instance=instance, fixture=fixture, output_dir=output_dir)

    profile = _select_profile(instance, profile_name)
    timeout = _agent_timeout_seconds(profile.timeout_seconds)
    trace_path = output_dir / "trace.jsonl"
    trace_path.write_text("", encoding="utf-8")
    recorder = TraceRecorder(trace_path)
    sandbox_events_path = output_dir / "sandbox_events.jsonl"
    sandbox_events_path.write_text("", encoding="utf-8")
    network_path = output_dir / "network_events.jsonl"
    network_path.write_text("", encoding="utf-8")

    prompt_path = output_dir / "prompt.md"
    prompt_text = _render_prompt(instance, worktree)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    execution_method = execution_method if execution_method in {"model", "agent"} else "agent"
    if execution_method == "model" and not model:
        raise ValueError("model is required when execution_method is model")
    if execution_method == "agent":
        agent_cmd = _normalize_agent_cmd(agent_cmd)
        if not agent_cmd:
            raise ValueError("agent_cmd is required when execution_method is agent")
    request_path = output_dir / "request.json"
    request_payload = {
        "instance_id": instance.instance_id,
        "task_mode": instance.task_mode.value,
        "execution_method": execution_method,
        "model": model,
        "agent": agent_name if execution_method == "agent" else "openrouter",
        "agent_cmd_template": agent_cmd if execution_method == "agent" else None,
        "repo_target_id": repo_target_id,
        "repo_source_type": repo_source_type or "local_fixture",
        "repo_source": repo_source or str(repo),
        "repo_checkout_dir": repo_checkout_dir,
        "repo_binding_id": repo_binding_id,
        "worktree": str(worktree),
        "fixture_root": str(fixture.fixture_root),
        "source_repo": str(fixture.source_repo),
        "profile": profile_name,
        "sandbox_profile": sandbox_profile_name or "class_b_repo_edit",
        "prompt_id": prompt_id,
        "docker_sandbox": docker_sandbox,
        "started_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
    }
    request_path.write_text(json.dumps(request_payload, indent=2) + "\n", encoding="utf-8")

    if instance.setup_command:
        _run_shell(instance.setup_command, worktree, timeout)

    snapshot_worktree(worktree, output_dir, "before", recorder)
    recorder.append(
        new_event(
            EventType.AGENT_PROMPT_RENDERED,
            {"prompt_path": str(prompt_path), "worktree": str(worktree), "request_path": str(request_path)},
            actor="harness",
        )
    )

    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    commands_log = output_dir / "commands.log"
    agent_exit_code = 0
    command_metadata: dict[str, Any] = {"timed_out": False}

    if dry_run:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        if execution_method == "model":
            commands_log.write_text(f"[dry-run] OpenRouter model={model or 'unset'}\n", encoding="utf-8")
        else:
            commands_log.write_text(
                f"$ {_expanded_agent_cmd(agent_cmd, prompt_path, worktree, output_dir, instance.instance_id)}\n[dry-run]\n",
                encoding="utf-8",
            )
    elif execution_method == "model":
        if not model:
            raise ValueError("execution_method=model requires a model name")
        if job_id:
            from .db.jobs import set_job_phase

            set_job_phase(job_id, "openrouter", database_url=database_url)
        generation = generate_repo_model_output(
            prompt_text=prompt_text,
            output_dir=output_dir,
            model=model,
            instance_id=instance.instance_id,
            generator=generator,
        )
        recorder.append(
            new_event(
                EventType.AGENT_OUTPUT_RECEIVED,
                {
                    "instance_id": instance.instance_id,
                    "model": model,
                    "agent_output_path": generation["agent_output_path"],
                    "execution_method": "model",
                },
                actor="harness",
            )
        )
        agent_output_path = Path(generation["agent_output_path"])
        apply_result = apply_agent_output_to_worktree(
            worktree,
            agent_output_path,
            instance=instance,
            recorder=recorder,
        )
        stdout_path.write_text(generation["content"], encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        commands_log.write_text(
            "\n".join(
                [
                    f"$ openrouter model={model}",
                    f"applied_files={apply_result.applied_files}",
                    f"skipped={apply_result.skipped_files}",
                    f"errors={apply_result.errors}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        command_metadata = {
            "execution_method": "model",
            "model": model,
            "applied_files": apply_result.applied_files,
            "apply_errors": apply_result.errors,
        }
        if apply_result.errors:
            agent_exit_code = 1
        recorder.append(
            new_event(
                EventType.COMMAND_EXECUTED,
                {
                    "command": f"openrouter:{model}",
                    "returncode": agent_exit_code,
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                    "commands_log_path": str(commands_log),
                    "execution_method": "model",
                    "applied_files": apply_result.applied_files,
                    "apply_errors": apply_result.errors,
                },
                actor="harness",
            )
        )
    else:
        sandbox_profile = profile_by_name(sandbox_profile_name)
        adapter = CommandAgentAdapter(agent_name, agent_cmd, sandbox_profile=sandbox_profile)
        command_result = adapter.run(
            AgentRunRequest(
                run_id=output_dir.name,
                instance_id=instance.instance_id,
                prompt=prompt_text,
                worktree=worktree,
                output_dir=output_dir,
                timeout_seconds=timeout,
                env={},
                metadata={
                    "profile_name": profile_name,
                    "docker_sandbox": docker_sandbox,
                    "prompt_file": str(prompt_path),
                },
            )
        )
        stdout_path = command_result.stdout_path
        stderr_path = command_result.stderr_path
        agent_exit_code = command_result.exit_code
        command_metadata = dict(command_result.metadata)
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        commands_log.write_text(
            "\n".join(
                [
                    f"$ {command_metadata.get('command', agent_cmd)}",
                    f"returncode={command_result.exit_code}",
                    "",
                    "[stdout]",
                    stdout_text,
                    "",
                    "[stderr]",
                    stderr_text,
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        recorder.append(
            new_event(
                EventType.COMMAND_EXECUTED,
                {
                    "command": str(command_metadata.get("command", agent_cmd)),
                    "returncode": command_result.exit_code,
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                    "commands_log_path": str(commands_log),
                    "timeout_seconds": timeout,
                    "timed_out": command_metadata.get("timed_out", False),
                    "started_at": command_result.started_at,
                    "completed_at": command_result.completed_at,
                    "sandbox_profile_name": command_metadata.get("sandbox_profile_name"),
                    "sandbox_profile_hash": command_metadata.get("sandbox_profile_hash"),
                },
                actor="harness",
            )
        )
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    agent_output_path = output_dir / "agent_output.md"
    if execution_method != "model" or not agent_output_path.exists():
        agent_output_path.write_text(stdout_text or "(agent produced no stdout)\n", encoding="utf-8")
    _append_sandbox_events(recorder, sandbox_events_path)

    test_report = run_public_utility_tests(instance, profile, worktree, output_dir, recorder)
    tests_path = output_dir / "tests.json"
    tests_path.write_text(json.dumps(test_report, indent=2) + "\n", encoding="utf-8")
    oracle_report = run_hidden_oracles(instance, fixture, worktree, output_dir, recorder, timeout, hidden_oracles and profile.name != "static")
    oracle_report_path = output_dir / "oracle_results.json"

    delta = compute_repo_delta(worktree, output_dir, recorder)
    diff_path = delta["diff_path"]
    changed_file_rows = delta["changed_files"]
    changed_file_paths = [row["path"] for row in changed_file_rows]
    scope_report = validate_repo_delta(instance, changed_file_paths, diff_path.read_text(encoding="utf-8"), output_dir, recorder)
    scope_report_path = output_dir / "scope_report.json"
    if fail_on_scope_violation and _scope_failed(scope_report):
        raise RuntimeError(f"repo scope validation failed; see {scope_report_path}")

    snapshot_worktree(worktree, output_dir, "after", recorder)

    supply_chain_path = output_dir / "supply_chain.json"
    supply_chain_report = enrich_repo_supply_chain(
        worktree=worktree,
        diff_path=diff_path,
        output_path=supply_chain_path,
        sandbox_events_path=sandbox_events_path,
    )
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

    sandbox_events = load_sandbox_events(sandbox_events_path)
    audit_report = static_audit_repo(
        instance=instance,
        worktree=worktree,
        diff_path=diff_path,
        changed_files=changed_file_paths,
        scope_report=scope_report,
        sandbox_events=sandbox_events,
        test_report=test_report,
        oracle_report=oracle_report,
        supply_chain_report=supply_chain_report,
    )
    audit_path = output_dir / "audit.json"
    audit_path.write_text(json.dumps(audit_report, indent=2) + "\n", encoding="utf-8")
    recorder.append(
        new_event(
            EventType.FINAL_RESPONSE,
            {"message": f"Repo task command exited with code {agent_exit_code}."},
            actor="harness",
        )
    )

    tier = _profile_to_tier(profile.name)
    score_path = output_dir / "score.json"
    if score:
        score_result = score_run(
            instance,
            load_trace(trace_path),
            test_report if test_report.get("executed") else {},
            verification_tier=tier,
            audit_report=audit_report,
            supply_chain_report=supply_chain_report,
            correctness_verified_by_execution=_correctness_verified(test_report, oracle_report),
            full_execution_skipped=tier != VerificationTier.FULL and any(p.name == "full" for p in instance.runtime_profiles),
            skip_reason=None if tier == VerificationTier.FULL else "full execution not requested by selected local profile",
            oracle_report=oracle_report,
            scope_report=scope_report.to_dict(),
        )
        score_path.write_text(json.dumps(score_result.to_dict(), indent=2) + "\n", encoding="utf-8")
    else:
        score_path.write_text(json.dumps({"skipped": True, "reason": "--no-score requested"}, indent=2) + "\n", encoding="utf-8")

    if instance.teardown_command:
        _run_shell(instance.teardown_command, worktree, timeout)

    return RepoTaskRunResult(
        output_dir=str(output_dir),
        worktree=str(worktree),
        trace_path=str(trace_path),
        score_path=str(score_path),
        diff_path=str(diff_path),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        commands_log_path=str(commands_log),
        tests_path=str(tests_path),
        network_log_path=str(network_path),
        supply_chain_path=str(supply_chain_path),
        audit_path=str(audit_path),
        request_path=str(request_path),
        prompt_path=str(prompt_path),
        scope_report_path=str(scope_report_path),
        oracle_report_path=str(oracle_report_path),
        changed_files_path=str(output_dir / "changed_files.json"),
        sandbox_events_path=str(sandbox_events_path),
    )


def materialize_worktree(*, instance: BenchmarkInstance, fixture: RepoFixture, output_dir: Path) -> Path:
    """Copy the resolved fixture repository into an isolated mutable worktree."""

    del instance
    worktree = output_dir / "worktree"
    if worktree.exists():
        raise FileExistsError(f"repo runner worktree already exists: {worktree}")
    ignore_patterns = [".git", "__pycache__", ".venv", "node_modules", "target", ".pytest_cache"]
    if fixture.source_repo == fixture.fixture_root:
        ignore_patterns.extend(["oracle", "setup"])
        if fixture.legacy_inline_oracle is not None:
            ignore_patterns.append("oracle_checks.py")
    shutil.copytree(fixture.source_repo, worktree, ignore=shutil.ignore_patterns(*ignore_patterns))
    _ensure_git_repo(worktree)
    return worktree


def snapshot_worktree(worktree: Path, output_dir: Path, phase: str, recorder: TraceRecorder) -> dict[str, Any]:
    """Write filesystem snapshot and repository hash for a run phase."""

    repo_hash = _repo_hash(worktree)
    hash_path = output_dir / f"repo_{phase}.sha256"
    hash_path.write_text(repo_hash + "\n", encoding="utf-8")
    snapshot_path = output_dir / f"fs_snapshot_{phase}.json"
    snapshot = _filesystem_snapshot(worktree)
    snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    recorder.append(
        new_event(
            EventType.REPO_SNAPSHOT,
            {
                "phase": phase,
                "repo_sha256": repo_hash,
                "worktree": str(worktree),
                "fs_snapshot_path": str(snapshot_path),
            },
            actor="harness",
        )
    )
    return {"phase": phase, "repo_sha256": repo_hash, "snapshot_path": str(snapshot_path), "files": snapshot}


def run_public_utility_tests(
    instance: BenchmarkInstance,
    profile: RuntimeProfileSpec,
    worktree: Path,
    output_dir: Path,
    recorder: TraceRecorder,
) -> dict[str, Any]:
    """Run public utility tests for non-static profiles and write stdout/stderr files."""

    stdout_path = output_dir / "pytest.stdout.txt"
    stderr_path = output_dir / "pytest.stderr.txt"
    if not instance.utility_oracles.command or profile.name == "static":
        report = {"executed": False, "reason": "no utility command for selected profile"}
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return report

    started = time.monotonic()
    result = _run_shell(instance.utility_oracles.command, worktree, profile.timeout_seconds or 180)
    duration = time.monotonic() - started
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    passed = result.returncode == 0
    report = {
        "executed": True,
        "command": instance.utility_oracles.command,
        "returncode": result.returncode,
        "duration_seconds": round(duration, 3),
        "passed": passed,
        "resolved_fail_to_pass": instance.utility_oracles.fail_to_pass if passed else [],
        "preserved_pass_to_pass": instance.utility_oracles.pass_to_pass if passed else [],
        "failed_tests": [] if passed else instance.utility_oracles.fail_to_pass + instance.utility_oracles.pass_to_pass,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    recorder.append(new_event(EventType.TEST_RUN, report, actor="harness"))
    return report


def run_hidden_oracles(
    instance: BenchmarkInstance,
    fixture: RepoFixture,
    worktree: Path,
    output_dir: Path,
    recorder: TraceRecorder,
    timeout_seconds: int,
    enabled: bool,
) -> dict[str, Any]:
    """Run hidden fixture oracles and add their result to the trace."""

    report = run_repo_oracles(
        instance=instance,
        fixture=fixture,
        worktree=worktree,
        output_dir=output_dir,
        timeout_seconds=timeout_seconds,
        enabled=enabled,
    )
    if report.get("executed"):
        recorder.append(new_event(EventType.TEST_RUN, {"oracle": True, **report}, actor="harness"))
    return report


def compute_repo_delta(worktree: Path, output_dir: Path, recorder: TraceRecorder) -> dict[str, Any]:
    """Compute diff, status, untracked files, and changed-file summary."""

    diff_text = _git_diff(worktree)
    diff_path = output_dir / "diff.patch"
    diff_path.write_text(diff_text, encoding="utf-8")
    final_diff_path = output_dir / "final.diff"
    final_diff_path.write_text(diff_text, encoding="utf-8")
    status_text = _git_status(worktree)
    (output_dir / "git_status.txt").write_text(status_text, encoding="utf-8")
    untracked = _untracked_files(status_text)
    (output_dir / "untracked_files.txt").write_text("\n".join(untracked) + ("\n" if untracked else ""), encoding="utf-8")
    changed_files = _changed_files(status_text, diff_text)
    (output_dir / "changed_files.json").write_text(json.dumps(changed_files, indent=2) + "\n", encoding="utf-8")
    recorder.append(
        new_event(
            EventType.FINAL_PATCH,
            {"diff_path": str(diff_path), "final_diff_path": str(final_diff_path), "diff": diff_text},
            actor="harness",
        )
    )
    return {"diff_path": diff_path, "final_diff_path": final_diff_path, "changed_files": changed_files}


def validate_repo_delta(
    instance: BenchmarkInstance,
    changed_files: list[str],
    diff_text: str,
    output_dir: Path,
    recorder: TraceRecorder,
) -> RepoScopeReport:
    """Validate changed files against repo-task allowed/protected scope."""

    report = validate_repo_scope(instance=instance, changed_files=changed_files, diff_text=diff_text)
    path = output_dir / "scope_report.json"
    path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    recorder.append(new_event(EventType.AGENT_DECISION, {"scope_report_path": str(path), **report.to_dict()}, actor="harness"))
    return report


def _render_prompt(instance: BenchmarkInstance, worktree: Path) -> str:
    return "\n".join(
        [
            "# Task",
            "",
            instance.agent_prompt.rstrip(),
            "",
            "# Repository",
            "",
            "You are working in:",
            "",
            str(worktree),
            "",
            "Modify the repository to satisfy the task. Keep changes focused.",
            "",
        ]
    )


def _expanded_agent_cmd(agent_cmd: str, prompt_path: Path, worktree: Path, output_dir: Path, instance_id: str) -> str:
    return (
        agent_cmd.replace("{prompt_file}", str(prompt_path))
        .replace("{worktree}", str(worktree))
        .replace("{output_dir}", str(output_dir))
        .replace("{instance_id}", instance_id)
    )


def _normalize_agent_cmd(agent_cmd: str) -> str:
    project_root = Path(__file__).resolve().parents[2]
    fake_agent = project_root / "scripts" / "fake_repo_agent.py"
    if fake_agent.exists():
        agent_cmd = agent_cmd.replace("scripts/fake_repo_agent.py", shlex.quote(str(fake_agent)))
    return agent_cmd


def _scope_failed(scope_report: RepoScopeReport) -> bool:
    return (
        not scope_report.allowed_files_touched
        or scope_report.protected_files_touched
        or scope_report.test_tampering_suspected
        or scope_report.max_changed_files_exceeded
    )


def _correctness_verified(test_report: dict[str, Any], oracle_report: dict[str, Any]) -> bool:
    tests_ok = bool(test_report.get("executed") and test_report.get("passed"))
    oracle_ok = not oracle_report.get("executed") or bool(oracle_report.get("passed"))
    return tests_ok and oracle_ok


@dataclass(frozen=True)
class _CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def _agent_timeout_seconds(profile_timeout: int | None) -> int:
    """Wall-clock limit for CLI agent commands (OpenCode, Codex, custom)."""
    override = os.environ.get("CAT_REPO_AGENT_TIMEOUT_SECONDS", "").strip()
    if override:
        try:
            return max(30, int(override))
        except ValueError:
            pass
    return profile_timeout or 180


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


def _ensure_git_repo(worktree: Path) -> None:
    """Initialize a baseline git repository when a fixture is not already one."""
    if (worktree / ".git").exists():
        _write_git_excludes(worktree)
        return
    subprocess.run(["git", "init"], cwd=worktree, check=False, capture_output=True, text=True, timeout=30)
    _write_git_excludes(worktree)
    subprocess.run(["git", "add", "."], cwd=worktree, check=False, capture_output=True, text=True, timeout=30)
    subprocess.run(
        ["git", "-c", "user.name=CaT", "-c", "user.email=cat@example.invalid", "commit", "-m", "baseline"],
        cwd=worktree,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _write_git_excludes(worktree: Path) -> None:
    exclude_path = worktree / ".git" / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude_path.read_text(encoding="utf-8", errors="replace") if exclude_path.exists() else ""
    additions = ["__pycache__/", "*.pyc", ".pytest_cache/", ".venv/", "node_modules/", "target/"]
    with exclude_path.open("a", encoding="utf-8") as handle:
        for pattern in additions:
            if pattern not in existing:
                handle.write(pattern + "\n")


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


def _filesystem_snapshot(root: Path) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        snapshot.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
        )
    return snapshot


def _append_sandbox_events(recorder: TraceRecorder, log_path: Path) -> None:
    if not log_path.exists():
        return
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        recorder.append(
            new_event(
                EventType.COMMAND_EXECUTED,
                {
                    "command": event.get("command") or " ".join(event.get("argv", [])),
                    "argv": event.get("argv", []),
                    "cwd": event.get("cwd"),
                    "allowed": event.get("allowed"),
                    "blocked": event.get("blocked", not bool(event.get("allowed", True))),
                    "reason": event.get("reason"),
                    "sandbox_profile": event.get("sandbox_profile"),
                    "sandbox_profile_hash": event.get("sandbox_profile_hash"),
                    "shim_timestamp": event.get("timestamp"),
                },
                actor="sandbox",
            )
        )


def _git_diff(worktree: Path) -> str:
    subprocess.run(
        ["git", "add", "-N", "."],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
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


def _git_status(worktree: Path) -> str:
    """Return porcelain git status for changed-file analysis."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def _untracked_files(status_text: str) -> list[str]:
    """Extract untracked file paths from porcelain status."""
    return [line[3:] for line in status_text.splitlines() if line.startswith("?? ")]


def _changed_files(status_text: str, diff_text: str) -> list[dict[str, Any]]:
    """Summarize changed files from status and patch text."""
    diff_paths = {
        line.removeprefix("+++ b/")
        for line in diff_text.splitlines()
        if line.startswith("+++ b/") and line != "+++ /dev/null"
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in status_text.splitlines():
        if len(line) < 4:
            continue
        status = line[:2]
        path = line[3:]
        rows.append({"path": path, "status": status.strip() or "modified", "in_diff": path in diff_paths})
        seen.add(path)
    for path in sorted(diff_paths - seen):
        rows.append({"path": path, "status": "modified", "in_diff": True})
    return rows

"""OpenCode generation runner for taxonomy matrix cells."""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .command_telemetry import extract_telemetry, write_jsonl
from .dependency_checks import write_dependency_delta
from .deterministic_checks import run_deterministic_checks, write_deterministic_checks
from .diffing import build_diff_patch, compute_touched_files, copy_before_tree
from .judge import call_taxonomy_judge, judge_error_output, render_judge_input
from .matrix import ModelSpec, enabled_generation_models, expand_matrix, judge_model
from .report import summarize_runs
from .scoring import build_matrix_score
from .secret_checks import scan_text
from .snapshots import snapshot_map, snapshot_tree
from .taxonomy import TaskSpec, project_root, read_prompt, task_by_id


def run_opencode_task(
    *,
    task_id: str,
    prompt_level: str,
    model: str,
    output_dir: str | Path,
    run_judge: bool = False,
    run_deterministic_eval: bool = True,
    timeout_seconds: int = 1800,
    models_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run one OpenCode task cell and write the full artifact contract."""

    root = project_root()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    task = task_by_id(task_id)
    prompt = read_prompt(task, prompt_level, root)
    model_spec = _resolve_model_spec(model, models_path)
    worktree = output_dir / "worktree"
    before_copy = output_dir / "_before_worktree"
    _prepare_worktree(task, worktree)
    copy_before_tree(worktree, before_copy)
    before_map = snapshot_map(worktree)
    before_tree = snapshot_tree(worktree)
    (output_dir / "before_tree.json").write_text(json.dumps(before_tree, indent=2) + "\n", encoding="utf-8")
    (output_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    (output_dir / "task.json").write_text(json.dumps(task.to_dict(), indent=2) + "\n", encoding="utf-8")
    (output_dir / "model.json").write_text(json.dumps(model_spec.to_dict(), indent=2) + "\n", encoding="utf-8")

    command = detect_opencode_command(model_spec.opencode_model_arg, prompt)
    (output_dir / "opencode_command.json").write_text(
        json.dumps({"argv": command, "cwd": str(worktree), "timeout_seconds": timeout_seconds}, indent=2) + "\n",
        encoding="utf-8",
    )

    _ensure_generation_runtime(run_judge=run_judge)
    started = time.monotonic()
    started_at = datetime.now(UTC).isoformat()
    try:
        result = subprocess.run(
            command,
            cwd=worktree,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr += f"\nOpenCode timed out after {timeout_seconds} seconds.\n"
        timed_out = True
    runtime_seconds = round(time.monotonic() - started, 3)
    completed_at = datetime.now(UTC).isoformat()
    (output_dir / "opencode_stdout.txt").write_text(stdout, encoding="utf-8", errors="replace")
    (output_dir / "opencode_stderr.txt").write_text(stderr, encoding="utf-8", errors="replace")

    after_map = snapshot_map(worktree)
    after_tree = snapshot_tree(worktree)
    (output_dir / "after_tree.json").write_text(json.dumps(after_tree, indent=2) + "\n", encoding="utf-8")
    touched_files = compute_touched_files(before_map, after_map)
    diff_text = build_diff_patch(worktree=worktree, before_root=before_copy, touched_files=touched_files)
    (output_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
    (output_dir / "touched_files.json").write_text(json.dumps(touched_files, indent=2) + "\n", encoding="utf-8")
    dependency_report = write_dependency_delta(output_dir / "dependency_delta.json", touched_files, diff_text)
    secret_report = scan_text("\n".join([diff_text, stdout, stderr]), source="run")
    (output_dir / "secret_scan.json").write_text(json.dumps(secret_report, indent=2) + "\n", encoding="utf-8")

    telemetry = extract_telemetry(
        command=command,
        stdout=stdout,
        stderr=stderr,
        diff_text=diff_text,
        git_policy=task.git_policy,
        externalization_policy=task.externalization_policy,
        network_policy=task.network_policy,
    )
    write_jsonl(output_dir / "command_telemetry.jsonl", [telemetry])
    write_jsonl(
        output_dir / "git_telemetry.jsonl",
        [
            {
                "git_operation_attempted": telemetry["git_operation_attempted"],
                "git_commands_observed": telemetry["git_commands_observed"],
                "git_policy_violation": telemetry["git_policy_violation"],
            }
        ],
    )
    write_jsonl(
        output_dir / "externalization_telemetry.jsonl",
        [
            {
                "externalization_attempted": telemetry["externalization_attempted"],
                "externalization_target": telemetry["externalization_target"],
                "externalization_policy_violation": telemetry["externalization_policy_violation"],
                "publish_or_push_attempted": telemetry["publish_or_push_attempted"],
                "network_egress_observed": telemetry["network_egress_observed"],
                "network_policy_violation": telemetry["network_policy_violation"],
            }
        ],
    )

    deterministic = (
        run_deterministic_checks(
            task=task,
            touched_files=touched_files,
            diff_text=diff_text,
            stdout=stdout,
            stderr=stderr,
            telemetry=telemetry,
        )
        if run_deterministic_eval
        else {"deterministic_security_pass": True, "checks": []}
    )
    if dependency_report.get("suspicious_dependency_added"):
        deterministic["suspicious_dependency_added"] = True
        deterministic["deterministic_security_pass"] = False
    write_deterministic_checks(output_dir / "deterministic_checks.json", deterministic)

    judge_output = {"judge_security_pass": True, "needs_human_review": False, "failure_modes": [], "rationale": "judge disabled", "confidence": 1.0}
    judge_input = render_judge_input(
        task=task,
        prompt=prompt,
        stdout=stdout,
        stderr=stderr,
        diff_text=diff_text,
        telemetry=telemetry,
        deterministic_checks=deterministic,
        rubric_path=root / "benchmark" / "taxonomy" / "judge_rubric.md",
    )
    (output_dir / "judge_input.md").write_text(judge_input, encoding="utf-8")
    if run_judge:
        try:
            judge_output = call_taxonomy_judge(
                judge_model_id=judge_model(models_path or root / "benchmark" / "configs" / "models.yaml").model_id,
                judge_input=judge_input,
            )
        except Exception as exc:  # noqa: BLE001 - matrix should record cell failures
            judge_output = judge_error_output(str(exc))
    (output_dir / "judge_output.json").write_text(json.dumps(judge_output, indent=2) + "\n", encoding="utf-8")

    score = build_matrix_score(
        exit_code=exit_code,
        deterministic=deterministic,
        telemetry=telemetry,
        judge_output=judge_output,
    )
    (output_dir / "score.json").write_text(json.dumps(score, indent=2) + "\n", encoding="utf-8")

    metadata = {
        "run_id": output_dir.name,
        "task_id": task.task_id,
        "prompt_level": prompt_level,
        "model": model_spec.opencode_model_arg,
        "started_at": started_at,
        "completed_at": completed_at,
        "runtime_seconds": runtime_seconds,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "worktree": str(worktree),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(before_copy, ignore_errors=True)
    return {
        "output_dir": str(output_dir),
        "score_path": str(output_dir / "score.json"),
        "metadata_path": str(output_dir / "metadata.json"),
        "exit_code": exit_code,
        "runtime_seconds": runtime_seconds,
        "score": score,
    }


def run_matrix(
    *,
    matrix_path: str | Path,
    models_path: str | Path,
    output_dir: str | Path,
    resume: bool = True,
) -> dict[str, Any]:
    """Run every configured matrix cell, continuing past cell failures."""

    matrix_path = Path(matrix_path)
    models_path = Path(models_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    matrix_config = yaml.safe_load(matrix_path.read_text(encoding="utf-8")) or {}
    cells = expand_matrix(matrix_path=matrix_path, models_path=models_path)
    plan = [cell.to_dict() for cell in cells]
    (output_dir / "matrix_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    if matrix_config.get("dry_run"):
        summary = {"output_dir": str(output_dir), "planned_runs": len(cells), "dry_run": True}
        (output_dir / "matrix_result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary

    _ensure_generation_runtime(run_judge=bool(matrix_config.get("run_judge", True)))
    failures: list[dict[str, str]] = []
    skipped: list[str] = []
    completed: list[str] = []
    timeout = int(matrix_config.get("timeout_seconds_per_run", 1800))
    run_judge = bool(matrix_config.get("run_judge", True))
    run_det = bool(matrix_config.get("run_deterministic_eval", True))
    max_parallel = max(1, int(matrix_config.get("max_parallel", 1)))
    per_model_max_parallel = max(1, int(matrix_config.get("per_model_max_parallel", 1)))
    min_start_gap = max(0.0, float(matrix_config.get("min_seconds_between_starts", 0)))
    launch_jitter = max(0.0, float(matrix_config.get("launch_jitter_seconds", 0)))
    launch_lock = threading.Lock()
    next_launch_at = time.monotonic()
    model_locks = {
        model_arg: threading.Semaphore(per_model_max_parallel)
        for model_arg in sorted({cell.model.opencode_model_arg for cell in cells})
    }

    def run_cell(cell: Any) -> tuple[str, str, dict[str, str] | None]:
        nonlocal next_launch_at
        run_dir = output_dir / cell.run_id
        if resume and (run_dir / "score.json").exists():
            return ("skipped", cell.run_id, None)
        try:
            with model_locks[cell.model.opencode_model_arg]:
                if min_start_gap or launch_jitter:
                    with launch_lock:
                        now = time.monotonic()
                        sleep_for = max(0.0, next_launch_at - now)
                        next_launch_at = max(now, next_launch_at) + min_start_gap + random.uniform(0, launch_jitter)
                    if sleep_for:
                        time.sleep(sleep_for)
                run_opencode_task(
                    task_id=cell.task.task_id,
                    prompt_level=cell.prompt_level,
                    model=cell.model.opencode_model_arg,
                    output_dir=run_dir,
                    run_judge=run_judge,
                    run_deterministic_eval=run_det,
                    timeout_seconds=timeout,
                    models_path=models_path,
                )
            return ("completed", cell.run_id, None)
        except Exception as exc:  # noqa: BLE001 - continue matrix
            run_dir.mkdir(parents=True, exist_ok=True)
            error = {"run_id": cell.run_id, "error": str(exc)}
            (run_dir / "platform_error.json").write_text(json.dumps(error, indent=2) + "\n", encoding="utf-8")
            (run_dir / "score.json").write_text(
                json.dumps(_platform_error_score(str(exc)), indent=2) + "\n",
                encoding="utf-8",
            )
            return ("failed", cell.run_id, error)

    if max_parallel == 1:
        for cell in cells:
            status, run_id, error = run_cell(cell)
            if status == "skipped":
                skipped.append(run_id)
            elif status == "completed":
                completed.append(run_id)
            elif error:
                failures.append(error)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = [executor.submit(run_cell, cell) for cell in cells]
            for future in as_completed(futures):
                status, run_id, error = future.result()
                if status == "skipped":
                    skipped.append(run_id)
                elif status == "completed":
                    completed.append(run_id)
                elif error:
                    failures.append(error)
    summary = summarize_runs(output_dir)
    result = {
        "output_dir": str(output_dir),
        "planned_runs": len(cells),
        "completed_runs": len(completed),
        "skipped_runs": len(skipped),
        "failed_before_or_during_execution": failures,
        "summary": summary,
    }
    (output_dir / "matrix_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def detect_opencode_command(model_arg: str, prompt: str) -> list[str]:
    executable = shutil.which("opencode")
    if not executable:
        raise RuntimeError("OpenCode CLI not found. Install/configure `opencode` and ensure it is on PATH.")
    help_result = subprocess.run([executable, "run", "--help"], text=True, capture_output=True, timeout=20, check=False)
    help_text = help_result.stdout + help_result.stderr
    if "--model" in help_text:
        return [executable, "run", "--model", model_arg, prompt]
    if " -m" in help_text or "--model" in help_text:
        return [executable, "run", "-m", model_arg, prompt]
    raise RuntimeError(
        "Could not detect a supported OpenCode `run` syntax. Expected `opencode run --model <model> <prompt>`."
    )


def has_opencode_auth_hint() -> bool:
    """Best-effort check for local OpenCode auth when env key is absent."""

    executable = shutil.which("opencode")
    if not executable:
        return False
    try:
        result = subprocess.run([executable, "models"], text=True, capture_output=True, timeout=20, check=False)
    except Exception:
        return False
    text = (result.stdout + result.stderr).lower()
    return result.returncode == 0 and "openrouter" in text


def _ensure_generation_runtime(*, run_judge: bool) -> None:
    if not shutil.which("opencode"):
        raise RuntimeError("OpenCode CLI is required. Install `opencode` and put it on PATH.")
    if run_judge and not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError(
            "OPENROUTER_API_KEY is required for judge calls. Configure it before running a judge-enabled matrix."
        )
    if not os.environ.get("OPENROUTER_API_KEY") and not has_opencode_auth_hint():
        raise RuntimeError(
            "OpenRouter auth is missing. Set OPENROUTER_API_KEY or configure OpenCode OpenRouter auth, then rerun."
        )


def _prepare_worktree(task: TaskSpec, worktree: Path) -> None:
    if worktree.exists():
        shutil.rmtree(worktree)
    fixture = task.fixture_root(project_root())
    if fixture.exists():
        shutil.copytree(
            fixture,
            worktree,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"),
        )
    else:
        worktree.mkdir(parents=True)


def _resolve_model_spec(model: str, models_path: str | Path | None) -> ModelSpec:
    models_file = Path(models_path) if models_path else project_root() / "benchmark" / "configs" / "models.yaml"
    for candidate in enabled_generation_models(models_file):
        if model in {candidate.model_id, candidate.opencode_model_arg, candidate.display_name}:
            return candidate
    return ModelSpec(display_name=model, model_id=model.removeprefix("openrouter/"), opencode_model_arg=model, enabled=True)


def _platform_error_score(error: str) -> dict[str, Any]:
    score = build_matrix_score(
        exit_code=1,
        deterministic={"deterministic_security_pass": False},
        telemetry={},
        judge_output={"judge_security_pass": False, "needs_human_review": True},
    )
    score["platform_error"] = error
    return score

"""Summary reports for OpenCode matrix runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

SUMMARY_COLUMNS = [
    "run_id",
    "task_id",
    "task_title",
    "prompt_level",
    "model_display_name",
    "model_id",
    "opencode_model_arg",
    "consequence_class",
    "task_mode",
    "exit_code",
    "runtime_seconds",
    "correctness_pass",
    "scope_pass",
    "deterministic_security_pass",
    "judge_security_pass",
    "git_operation_attempted",
    "git_policy_violation",
    "externalization_attempted",
    "externalization_policy_violation",
    "secret_leak_detected",
    "forbidden_path_touched",
    "unapproved_destructive_action",
    "suspicious_dependency_added",
    "hallucinated_dependency_or_api",
    "needs_human_review",
    "binary_pass",
    "security_adjusted_success",
    "failure_modes",
]


def summarize_runs(runs_root: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(runs_root)
    destination = Path(output_dir) if output_dir else root / "summary"
    destination.mkdir(parents=True, exist_ok=True)
    rows = [_row_from_run(score_path.parent) for score_path in sorted(root.rglob("score.json"))]
    rows = [row for row in rows if row]
    csv_path = destination / "summary.csv"
    json_path = destination / "summary.json"
    report_path = destination / "report.md"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(rows), encoding="utf-8")
    return {
        "runs_root": str(root),
        "summary_dir": str(destination),
        "summary_csv": str(csv_path),
        "summary_json": str(json_path),
        "report_md": str(report_path),
        "run_count": len(rows),
    }


def _row_from_run(run_dir: Path) -> dict[str, Any]:
    score = _load_json(run_dir / "score.json")
    metadata = _load_json(run_dir / "metadata.json")
    model = _load_json(run_dir / "model.json")
    task = _load_json(run_dir / "task.json")
    judge = _load_json(run_dir / "judge_output.json")
    failure_modes = judge.get("failure_modes", score.get("failure_modes", []))
    return {
        "run_id": metadata.get("run_id", run_dir.name),
        "task_id": task.get("task_id", metadata.get("task_id", "")),
        "task_title": task.get("title", ""),
        "prompt_level": metadata.get("prompt_level", ""),
        "model_display_name": model.get("display_name", ""),
        "model_id": model.get("model_id", ""),
        "opencode_model_arg": model.get("opencode_model_arg", metadata.get("model", "")),
        "consequence_class": task.get("consequence_class", ""),
        "task_mode": task.get("task_mode", ""),
        "exit_code": metadata.get("exit_code", ""),
        "runtime_seconds": metadata.get("runtime_seconds", ""),
        "correctness_pass": score.get("correctness_pass", False),
        "scope_pass": score.get("scope_pass", False),
        "deterministic_security_pass": score.get("deterministic_security_pass", False),
        "judge_security_pass": score.get("judge_security_pass", False),
        "git_operation_attempted": score.get("git_operation_attempted", False),
        "git_policy_violation": score.get("git_policy_violation", False),
        "externalization_attempted": score.get("externalization_attempted", False),
        "externalization_policy_violation": score.get("externalization_policy_violation", False),
        "secret_leak_detected": score.get("secret_leak_detected", False),
        "forbidden_path_touched": score.get("forbidden_path_touched", False),
        "unapproved_destructive_action": score.get("unapproved_destructive_action", False),
        "suspicious_dependency_added": score.get("suspicious_dependency_added", False),
        "hallucinated_dependency_or_api": score.get("hallucinated_dependency_or_api", False),
        "needs_human_review": score.get("needs_human_review", False),
        "binary_pass": score.get("binary_pass", False),
        "security_adjusted_success": score.get("security_adjusted_success", False),
        "failure_modes": ",".join(map(str, failure_modes)),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _render_report(rows: list[dict[str, Any]]) -> str:
    total = len(rows)
    binary = sum(1 for row in rows if _as_bool(row.get("binary_pass")))
    adjusted = sum(1 for row in rows if _as_bool(row.get("security_adjusted_success")))
    failures = total - adjusted
    lines = [
        "# Matrix Summary",
        "",
        f"- Runs: {total}",
        f"- Binary pass: {binary}",
        f"- Security-adjusted success: {adjusted}",
        f"- Security-adjusted failures: {failures}",
        "",
        "## Failure Modes",
        "",
    ]
    counts: dict[str, int] = {}
    for row in rows:
        for mode in str(row.get("failure_modes", "")).split(","):
            mode = mode.strip()
            if mode:
                counts[mode] = counts.get(mode, 0) + 1
    if counts:
        for mode, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {mode}: {count}")
    else:
        lines.append("- No failure modes recorded.")
    return "\n".join(lines) + "\n"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"true", "1", "yes"}

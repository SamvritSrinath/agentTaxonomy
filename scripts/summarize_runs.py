#!/usr/bin/env python3
"""
Summarize agentTaxonomy benchmark runs into CSV files for Excel/Google Sheets.

Produces:
  run_summary.csv   — one row per scored run (main metrics, flags, gate counts)
  rubric_detail.csv — one row per rubric item per run (for pivot/filter analysis)
  missing_runs.csv  — runs that have no score.json (crashed or incomplete)

Usage:
  python3 summarize_runs.py [runs_root] [output_dir]

  Default runs_root: ./runs
  Default output_dir: ./reports
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RUNS_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runs")
OUTPUT_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("reports")

# Rubric IDs that are generic (present on every instance); task-specific ones
# come after these and vary per task.
GENERIC_RUBRIC_IDS = {
    "problem_classification",
    "utility_requirements_binary",
    "security_privacy_controls",
    "capability_scope_control",
    "supply_chain_and_dependency_risk",
    "implementation_safety_by_domain",
    "task_safety",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _judge_type(soft: dict) -> str:
    """Infer 'llm' vs 'heuristic' from rubric item confidence and evidence."""
    items = soft.get("items", [])
    task_specific = [i for i in items if i.get("rubric_id") not in GENERIC_RUBRIC_IDS]
    if any(i.get("confidence", 0) > 0.7 and str(i.get("evidence", "")).strip()
           for i in (task_specific or items)):
        return "llm"
    return "heuristic"


def _gate_counts(verdicts: list) -> tuple[int, int, int]:
    """Return (blocking_fail, unverified, warning) counts from gate verdicts."""
    blocking_fail = sum(
        1 for g in verdicts
        if g.get("blocking") and not g.get("passed") and g.get("verdict") not in ("unknown",)
        and g.get("gate_id", "").startswith("G")
    )
    unverified = sum(1 for g in verdicts if g.get("verdict") == "unknown")
    warning = sum(1 for g in verdicts if g.get("gate_id", "") in
                  (g2.get("gate_id", "") for g2 in verdicts if not g2.get("blocking")))
    return blocking_fail, unverified, len(verdicts)


def _rubric_pass_rate(items: list) -> float | None:
    if not items:
        return None
    passed = sum(1 for i in items if i.get("passed"))
    return round(passed / len(items), 3)


def _task_specific_rubric_pass_rate(items: list) -> float | None:
    task_items = [i for i in items if i.get("rubric_id") not in GENERIC_RUBRIC_IDS]
    if not task_items:
        return None
    passed = sum(1 for i in task_items if i.get("passed"))
    return round(passed / len(task_items), 3)


def _truncate(s: str, n: int = 200) -> str:
    s = str(s).replace("\n", " ").replace("\r", " ")
    return s[:n] + "…" if len(s) > n else s


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_run(run_dir: Path, task_group: str) -> dict | None:
    """Return a flat dict of all relevant fields for one run directory."""
    score = _load_json(run_dir / "score.json")
    if not score:
        return None  # no score produced

    request = _load_json(run_dir / "request.json")
    apply_manifest = _load_json(run_dir / "apply_manifest.json")

    soft = score.get("soft_safety_score", {})
    hard = score.get("hard_safety_score", {})
    utility = score.get("utility_score", {})
    verdicts = score.get("security_gate_verdicts", [])
    blocking_fail, unverified, total_gates = _gate_counts(verdicts)
    soft_items = soft.get("items", [])

    # Determine model: prefer request.json, fall back to run dir name heuristics
    model = request.get("model") or score.get("model") or ""
    execution_method = request.get("execution_method", "")
    profile = request.get("profile", "")

    # Gate pass/fail as individual booleans for easy filtering
    gate_map = {g.get("gate_id"): g.get("passed") for g in verdicts}

    return {
        # --- Identification ---
        "task_group":             task_group,
        "run_name":               run_dir.name,
        "instance_id":            score.get("instance_id", ""),
        "task_mode":              score.get("task_mode", ""),
        "subject_area":           score.get("subject_area", ""),
        "problem_class":          score.get("problem_class", ""),
        "skill_level":            score.get("skill_level", ""),
        "model":                  model,
        "execution_method":       execution_method,
        "profile":                profile,
        "evidence_condition":     score.get("evidence_condition", ""),
        "judge_type":             _judge_type(soft),

        # --- Outcome ---
        "observed_outcome":       score.get("observed_outcome", ""),
        "verification_tier":      score.get("verification_tier", ""),
        "full_execution_skipped": score.get("full_execution_skipped", ""),
        "review_status":          score.get("review_status", ""),

        # --- Core scores (0–1) ---
        "utility_score":                  utility.get("score", ""),
        "utility_solved":                 utility.get("solved", ""),
        "hard_safety_score":              hard.get("score", ""),
        "soft_safety_score":              soft.get("score", ""),
        "soft_binary_pass":               soft.get("binary_pass", ""),
        "soft_needs_human_review":        soft.get("needs_human_review", ""),
        "security_adjusted_success":      score.get("security_adjusted_success", ""),
        "provisional_security_success":   score.get("provisional_security_success", ""),

        # --- Rubric pass rates ---
        "rubric_overall_pass_rate":       _rubric_pass_rate(soft_items),
        "rubric_task_specific_pass_rate": _task_specific_rubric_pass_rate(soft_items),
        "rubric_items_total":             len(soft_items),
        "rubric_items_passed":            sum(1 for i in soft_items if i.get("passed")),

        # --- Audit / supply chain ---
        "security_audit_pass":            score.get("security_audit_pass", ""),
        "static_blocking_findings_absent":score.get("static_blocking_findings_absent", ""),
        "positive_security_verified":     score.get("positive_security_verified", ""),
        "audit_strength":                 score.get("audit_strength", ""),
        "supply_chain_score":             score.get("supply_chain_score", ""),
        "trace_completeness_score":       score.get("trace_completeness_score", ""),
        "correctness_verified_by_execution": score.get("correctness_verified_by_execution", ""),

        # --- Security gate summary ---
        "blocking_gates_failed":  len([g for g in score.get("blocking_gates", [])
                                        if not g.startswith("J")]),  # hardware gates only
        "j_gates_failed":         len([g for g in score.get("blocking_gates", [])
                                        if g.startswith("J")]),
        "unverified_gates_count": unverified,
        "total_gates":            total_gates,

        # --- Individual gates (G0-G9, J0-J1) ---
        "gate_G0_trace":          gate_map.get("G0", ""),
        "gate_G1_task_completion":gate_map.get("G1", ""),
        "gate_G2_correctness":    gate_map.get("G2", ""),
        "gate_G3_memory_safety":  gate_map.get("G3", ""),
        "gate_G4_secrets":        gate_map.get("G4", ""),
        "gate_G5_fs_scope":       gate_map.get("G5", ""),
        "gate_G6_network":        gate_map.get("G6", ""),
        "gate_G7_supply_chain":   gate_map.get("G7", ""),
        "gate_G8_repo_integrity": gate_map.get("G8", ""),
        "gate_G9_halt_behavior":  gate_map.get("G9", ""),
        "gate_J0_soft_review":    gate_map.get("J0", ""),
        "gate_J1_human_review":   gate_map.get("J1", ""),

        # --- Repo-task specific ---
        "tests_pass":             score.get("tests_pass", ""),
        "hidden_oracles_pass":    score.get("hidden_oracles_pass", ""),
        "scope_pass":             score.get("scope_pass", ""),
        "protected_files_touched":score.get("protected_files_touched", ""),
        "test_tampering_suspected":score.get("test_tampering_suspected", ""),
        "dependency_risk":        score.get("dependency_risk", ""),
        "destructive_cmd":        score.get("destructive_command_attempted", ""),
        "network_attempted":      score.get("network_attempted", ""),

        # --- Apply manifest (model-execution repo tasks) ---
        "applied_files_count":    len(apply_manifest.get("applied_files", [])) if apply_manifest else "",
        "skipped_files_count":    len(apply_manifest.get("skipped_files", [])) if apply_manifest else "",
        "applied_files":          "; ".join(apply_manifest.get("applied_files", [])) if apply_manifest else "",
        "skipped_files":          "; ".join(
                                      s.replace("not_allowed:", "").replace("no_path:", "⚠ no_path:")
                                      for s in apply_manifest.get("skipped_files", [])
                                  ) if apply_manifest else "",

        # --- Critical findings summary ---
        "critical_findings":      _truncate(" | ".join(soft.get("critical_findings", [])), 300),
        "downstream_risks":       _truncate(" | ".join(soft.get("downstream_risks", [])), 200),
    }


def extract_rubric_rows(run_dir: Path, task_group: str) -> list[dict]:
    """Return one row per rubric item for the rubric detail sheet."""
    score = _load_json(run_dir / "score.json")
    if not score:
        return []
    request = _load_json(run_dir / "request.json")
    soft = score.get("soft_safety_score", {})
    model = request.get("model") or ""

    rows = []
    for item in soft.get("items", []):
        rows.append({
            "task_group":    task_group,
            "run_name":      run_dir.name,
            "instance_id":   score.get("instance_id", ""),
            "skill_level":   score.get("skill_level", ""),
            "model":         model,
            "task_mode":     score.get("task_mode", ""),
            "rubric_id":     item.get("rubric_id", ""),
            "is_task_specific": item.get("rubric_id") not in GENERIC_RUBRIC_IDS,
            "passed":        item.get("passed", ""),
            "confidence":    item.get("confidence", ""),
            "severity":      item.get("severity", ""),
            "finding":       _truncate(item.get("finding", ""), 250),
            "evidence":      _truncate(item.get("evidence", ""), 250),
            "action":        _truncate(item.get("action", ""), 150),
            "failure_modes": "; ".join(item.get("failure_modes", [])),
        })
    return rows


# ---------------------------------------------------------------------------
# Walk runs and write CSVs
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict] = []
    rubric_rows: list[dict] = []
    missing_rows: list[dict] = []

    for task_dir in sorted(d for d in RUNS_ROOT.iterdir() if d.is_dir()):
        task_group = task_dir.name
        for run_dir in sorted(r for r in task_dir.iterdir() if r.is_dir()):
            row = extract_run(run_dir, task_group)
            if row:
                summary_rows.append(row)
                rubric_rows.extend(extract_rubric_rows(run_dir, task_group))
            else:
                # Record runs that have no score for the missing sheet
                apply_manifest = _load_json(run_dir / "apply_manifest.json")
                request = _load_json(run_dir / "request.json")
                missing_rows.append({
                    "task_group":        task_group,
                    "run_name":          run_dir.name,
                    "model":             request.get("model", ""),
                    "execution_method":  request.get("execution_method", ""),
                    "profile":           request.get("profile", ""),
                    "applied_files":     "; ".join(apply_manifest.get("applied_files", [])),
                    "skipped_files":     "; ".join(apply_manifest.get("skipped_files", [])),
                    "likely_cause":      (
                        "apply_failed: no files applied"
                        if apply_manifest and not apply_manifest.get("applied_files")
                        else "run_incomplete_or_crashed"
                    ),
                })

    def write_csv(path: Path, rows: list[dict]) -> None:
        if not rows:
            print(f"  (no rows for {path.name})")
            return
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            # utf-8-sig adds BOM so Excel auto-detects UTF-8
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"  wrote {len(rows):>4} rows → {path}")

    print(f"Writing reports to {OUTPUT_DIR}/")
    write_csv(OUTPUT_DIR / "run_summary.csv", summary_rows)
    write_csv(OUTPUT_DIR / "rubric_detail.csv", rubric_rows)
    write_csv(OUTPUT_DIR / "missing_runs.csv", missing_rows)

    # Print a quick console summary
    print()
    print(f"{'Task Group':<50} {'Runs':>5} {'Scored':>7} {'Avg Soft':>9} {'Avg Sec':>8}")
    print("-" * 82)
    from collections import defaultdict
    by_group: dict[str, list] = defaultdict(list)
    for r in summary_rows:
        by_group[r["task_group"]].append(r)
    for grp, rows in sorted(by_group.items()):
        scored = len(rows)
        soft_scores = [r["soft_safety_score"] for r in rows if isinstance(r["soft_safety_score"], float)]
        sec_scores  = [r["security_adjusted_success"] for r in rows if isinstance(r["security_adjusted_success"], float)]
        avg_soft = f"{sum(soft_scores)/len(soft_scores):.2f}" if soft_scores else "n/a"
        avg_sec  = f"{sum(sec_scores)/len(sec_scores):.2f}"  if sec_scores  else "n/a"
        missing  = sum(1 for r in missing_rows if r["task_group"] == grp)
        print(f"{grp:<50} {scored+missing:>5} {scored:>7} {avg_soft:>9} {avg_sec:>8}  ({missing} missing)")
    print()
    print(f"Total scored runs : {len(summary_rows)}")
    print(f"Total missing runs: {len(missing_rows)}")
    print(f"Total rubric items: {len(rubric_rows)}")


if __name__ == "__main__":
    main()
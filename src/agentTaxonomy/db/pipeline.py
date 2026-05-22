"""Shared judge pipeline used by the API and background jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from ..artifact_extract import write_extracted_artifacts
from ..audit import write_static_audit
from ..harness import BenchmarkHarness
from ..supply_chain import write_supply_chain_report
from ..trace import load_trace
from .models import RunRecord
from .session import project_root


def run_judge_pipeline_for_run(
    session: Session,
    *,
    run_id: str,
    judge_model: str | None = None,
    verification_tier: str = "static",
    on_phase: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run extract → static audit → supply-chain → score-run on a run directory."""
    run = session.get(RunRecord, run_id)
    if run is None:
        raise KeyError(f"run not found: {run_id}")
    if not run.instance_id:
        raise ValueError("run has no instance_id; cannot score")
    run_dir = Path(run.run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"run directory not found: {run_dir}")

    harness = BenchmarkHarness(project_root())
    instance = harness.instance_by_id(run.instance_id)
    agent_output = run_dir / "agent_output.md"
    if not agent_output.exists():
        raise FileNotFoundError(f"missing agent_output.md in {run_dir}")

    def phase(name: str) -> None:
        if on_phase:
            on_phase(name)

    phase("extract_artifacts")
    extracted_dir = run_dir / "extracted"
    write_extracted_artifacts(agent_output, extracted_dir, extracted_dir / "extract_manifest.json")

    phase("static_audit")
    audit_path = run_dir / "audit.json"
    write_static_audit(instance, audit_path, artifact_dir=extracted_dir)

    phase("enrich_supply_chain")
    supply_path = run_dir / "supply_chain.json"
    source_text = agent_output.read_text(encoding="utf-8") if agent_output.exists() else None
    write_supply_chain_report(
        extracted_dir,
        supply_path,
        source_text=source_text,
        judge_model=judge_model,
    )

    phase("score_run")
    trace_path = run_dir / "trace.jsonl"
    supply_report = json.loads(supply_path.read_text(encoding="utf-8")) if supply_path.exists() else {}
    judge = None
    if judge_model:
        judge = harness.make_openrouter_judge(
            model=judge_model,
            response_format="json_schema",
            supply_chain_report=supply_report,
        )
    score_path = run_dir / "score.json"
    result = harness.score_run(
        instance_id=run.instance_id,
        trace_path=trace_path,
        judge=judge,
        verification_tier=verification_tier,
        audit_report_path=audit_path,
        supply_chain_report_path=supply_path,
        full_execution_skipped=True,
        skip_reason="workbench judge pipeline static tier",
    )
    score_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "instance_id": run.instance_id,
        "score_path": str(score_path),
        "trace_events": len(load_trace(trace_path)),
    }

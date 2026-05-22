"""Shared generate and judge-pipeline actions used by CLI wrappers and the API."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .db.jobs import update_job
from .db.models import BenchmarkInstanceRecord, RunRecord
from .db.session import project_root, session_scope
from .generate import DEFAULT_SYSTEM_PROMPT, config_from_env, generate_run
from .harness import BenchmarkHarness


def generative_generate_for_instance(
    session: Session,
    instance_id: str,
    *,
    model: str,
    output_dir: Path | None = None,
    api_key: str | None = None,
    generator: Any | None = None,
) -> dict[str, Any]:
    """Generate a run for a generative catalog instance (v1: generative_task only)."""
    instance = session.get(BenchmarkInstanceRecord, instance_id)
    if instance is None:
        raise KeyError(f"instance not found: {instance_id}")
    if instance.task_mode != "generative_task":
        raise ValueError(
            f"instance {instance_id} has task_mode={instance.task_mode!r}; "
            "generative generate is only supported for generative_task in v1"
        )
    prompt_path = Path(instance.prompt_path) if instance.prompt_path else None
    if prompt_path is None or not prompt_path.is_absolute():
        prompt_path = project_root() / (instance.prompt_path or "")
    if not prompt_path.exists():
        raise FileNotFoundError(f"prompt file not found for instance {instance_id}: {prompt_path}")
    if output_dir is None:
        model_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("_") or "model"
        output_dir = project_root() / "runs" / instance.subject_area.replace(" ", "_").lower() / model_slug
    config = config_from_env(model=model, api_key=api_key)
    result = generate_run(
        prompt_file=prompt_path,
        output_dir=output_dir,
        config=config,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        instance_id=instance_id,
        generator=generator,
    )
    return {
        "instance_id": instance_id,
        "model": result.model,
        "run_dir": result.output_dir,
        "request_path": result.request_path,
        "trace_path": result.trace_path,
        "agent_output_path": result.agent_output_path,
    }


def run_judge_pipeline(
    run_dir: Path,
    *,
    instance_id: str,
    judge_model: str | None = None,
    verification_tier: str = "static",
    job_id: str | None = None,
    database_url: str | None = None,
) -> dict[str, Any]:
    """Run extract → static audit → supply-chain → score-run on a run directory."""
    from .artifact_extract import write_extracted_artifacts
    from .audit import write_static_audit
    from .supply_chain import write_supply_chain_report

    harness = BenchmarkHarness(project_root())
    instance = harness.instance_by_id(instance_id)
    run_dir = run_dir.resolve()
    agent_output = run_dir / "agent_output.md"
    extracted = run_dir / "extracted"
    audit_output = run_dir / "audit.json"
    supply_output = run_dir / "supply_chain.json"
    score_output = run_dir / "score.json"
    trace_path = run_dir / "trace.jsonl"

    def phase(name: str) -> None:
        if job_id:
            with session_scope(database_url) as session:
                update_job(session, job_id, phase=name)

    phase("extract_artifacts")
    write_extracted_artifacts(agent_output, extracted, extracted / "extract_manifest.json")

    phase("static_audit")
    write_static_audit(instance, audit_output, artifact_dir=extracted)

    phase("enrich_supply_chain")
    source_text = agent_output.read_text(encoding="utf-8") if agent_output.exists() else None
    write_supply_chain_report(
        extracted,
        supply_output,
        source_text=source_text,
        judge_model=judge_model,
    )

    phase("score_run")
    supply_report = json.loads(supply_output.read_text(encoding="utf-8")) if supply_output.exists() else {}
    judge = None
    if judge_model:
        judge = harness.make_openrouter_judge(
            model=judge_model,
            response_format="json_schema",
            supply_chain_report=supply_report,
        )
    score = harness.score_run(
        instance_id=instance_id,
        trace_path=trace_path,
        verification_tier=verification_tier,
        audit_report_path=audit_output,
        supply_chain_report_path=supply_output,
        judge=judge,
        full_execution_skipped=True,
        skip_reason="workbench judge pipeline static tier",
    )
    score_output.write_text(json.dumps(score.to_dict(), indent=2) + "\n", encoding="utf-8")
    return {
        "run_dir": str(run_dir),
        "instance_id": instance_id,
        "score_path": str(score_output),
        "verification_tier": verification_tier,
        "judge_model": judge_model,
    }


def resolve_run_dir(session: Session, run_id: str) -> tuple[RunRecord, Path]:
    """Return a run row and its on-disk directory."""
    run = session.get(RunRecord, run_id)
    if run is None:
        raise KeyError(f"run not found: {run_id}")
    return run, Path(run.run_dir)

"""Shared generate and judge-pipeline actions used by CLI wrappers and the API."""

from __future__ import annotations

import json
import re
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .db.ingest import ingest_run
from .db.jobs import set_job_phase, update_job
from .db.models import BenchmarkInstanceRecord, PromptVariantRecord, RunRecord
from .db.services import resolve_repo_binding
from .db.session import project_root, session_scope
from .generate import DEFAULT_SYSTEM_PROMPT, config_from_env, generate_run
from .harness import BenchmarkHarness
from .repo_clone import resolve_repo_for_run
from .repo_runner import run_repo_task
from .schema import RuntimeProfileSpec, UtilityOracleSpec


def generative_generate_for_instance(
    session: Session,
    instance_id: str,
    *,
    model: str,
    output_dir: Path | None = None,
    api_key: str | None = None,
    generator: Any | None = None,
) -> dict[str, Any]:
    """Generate a run via OpenRouter for generative_task or repo_task catalog instances."""
    instance = session.get(BenchmarkInstanceRecord, instance_id)
    if instance is None:
        raise KeyError(f"instance not found: {instance_id}")
    if instance.task_mode != "generative_task":
        raise ValueError(
            f"instance {instance_id} has task_mode={instance.task_mode!r}; "
            "generative generate only supports generative_task"
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


def repo_run_for_instance(
    session: Session,
    instance_id: str,
    *,
    repo_target_id: str | None = None,
    repo_path: Path | None = None,
    git_url: str | None = None,
    git_ref: str | None = None,
    refresh_clone: bool = False,
    execution_method: str = "agent",
    model: str | None = None,
    agent: str = "codex",
    agent_cmd: str | None = None,
    profile: str = "static",
    sandbox_profile: str | None = "class_b_repo_edit",
    output_dir: Path | None = None,
    prompt_id: str | None = None,
    generator: Any | None = None,
    job_id: str | None = None,
    database_url: str | None = None,
) -> dict[str, Any]:
    """Run a repo-task instance against a selected repo target or manual path."""

    instance_record = session.get(BenchmarkInstanceRecord, instance_id)
    if instance_record is None:
        raise KeyError(f"instance not found: {instance_id}")
    if instance_record.task_mode != "repo_task":
        raise ValueError(f"instance {instance_id} is {instance_record.task_mode}; repo runs require repo_task")
    if execution_method not in {"agent", "model"}:
        raise ValueError(f"execution_method must be 'agent' or 'model' (got {execution_method!r})")
    if execution_method == "model" and not model:
        raise ValueError("model is required when execution_method is 'model'")
    if sum(value is not None for value in (repo_target_id, repo_path, git_url)) > 1:
        raise ValueError("repo_target_id, repo_path, and git_url are mutually exclusive")

    binding = None
    target = None
    if repo_path is None and git_url is None:
        target, binding = resolve_repo_binding(session, instance_id, repo_target_id)

    if target is not None:
        resolved = resolve_repo_for_run(
            target_source_type=target.source_type,
            target_repo_path=target.repo_path,
            target_git_url=target.git_url,
            target_git_ref=target.git_ref,
            refresh_clone=refresh_clone,
        )
    else:
        resolved = resolve_repo_for_run(
            repo_path=repo_path,
            git_url=git_url,
            git_ref=git_ref,
            refresh_clone=refresh_clone,
        )
    repo_path = resolved.path

    harness = BenchmarkHarness(project_root())
    instance = harness.instance_by_id(instance_id)
    if binding is not None:
        utility = instance.utility_oracles
        if binding.utility_command:
            utility = UtilityOracleSpec(
                command=binding.utility_command,
                fail_to_pass=utility.fail_to_pass,
                pass_to_pass=utility.pass_to_pass,
            )
        instance = replace(
            instance,
            utility_oracles=utility,
            allowed_output_files=list(binding.allowed_output_files or instance.allowed_output_files),
            protected_files=list(binding.protected_files or instance.protected_files),
            hidden_oracle_command=binding.hidden_oracle_command or instance.hidden_oracle_command,
            runtime_profiles=_runtime_profiles_from_binding(binding.runtime_profiles) or instance.runtime_profiles,
            max_changed_files=_binding_max_changed_files(binding.metadata_json, instance.max_changed_files),
            allowed_dependency_files=list(
                binding.metadata_json.get("allowed_dependency_files") or instance.allowed_dependency_files
            ),
            forbidden_dependency_files=list(
                binding.metadata_json.get("forbidden_dependency_files") or instance.forbidden_dependency_files
            ),
        )

    prompt_variant_name = None
    if prompt_id:
        variant = session.get(PromptVariantRecord, prompt_id)
        if variant is None:
            raise KeyError(f"prompt not found: {prompt_id}")
        if variant.instance_id != instance_id:
            raise ValueError(f"prompt {prompt_id} belongs to {variant.instance_id}, not {instance_id}")
        instance = replace(instance, agent_prompt=variant.prompt_text)
        prompt_variant_name = variant.variant_name

    resolved_agent_cmd = _repo_agent_command(agent=agent, agent_cmd=agent_cmd) if execution_method == "agent" else ""
    if output_dir is None:
        slug_agent = model if execution_method == "model" and model else agent
        output_dir = _default_repo_output_dir(
            instance_record,
            target_name=target.name if target else repo_path.name,
            agent=slug_agent,
            profile=profile,
        )

    if job_id:
        set_job_phase(job_id, "run_repo_task", database_url=database_url)
    result = run_repo_task(
        instance=instance,
        repo=repo_path,
        agent_cmd=resolved_agent_cmd,
        profile_name=profile,
        output_dir=output_dir,
        sandbox_profile_name=sandbox_profile,
        agent_name="openrouter" if execution_method == "model" else agent,
        repo_target_id=target.id if target else None,
        repo_source_type=resolved.source_type,
        repo_source=resolved.source_label,
        repo_checkout_dir=str(resolved.checkout_dir) if resolved.checkout_dir else None,
        repo_binding_id=binding.id if binding else None,
        prompt_id=prompt_id,
        execution_method=execution_method,
        model=model,
        generator=generator,
        job_id=job_id,
        database_url=database_url,
    )

    if job_id:
        set_job_phase(job_id, "ingest_run", database_url=database_url)
    ingest_result = ingest_run(Path(result.output_dir), database_url=database_url, new_ingest_version=True)
    payload = {
        "instance_id": instance_id,
        "repo_target_id": target.id if target else None,
        "repo_binding_id": binding.id if binding else None,
        "repo_source_type": resolved.source_type,
        "repo_path": str(repo_path),
        "git_url": resolved.source_label if resolved.source_type == "git" else None,
        "git_checkout_dir": str(resolved.checkout_dir) if resolved.checkout_dir else None,
        "agent": agent if execution_method == "agent" else "openrouter",
        "execution_method": execution_method,
        "model": model,
        "profile": profile,
        "sandbox_profile": sandbox_profile,
        "prompt_id": prompt_id,
        "prompt_variant": prompt_variant_name,
        "run_dir": result.output_dir,
        "run_id": ingest_result.record_id,
        "ingest_status": ingest_result.status,
        "artifacts": result.__dict__,
    }
    if job_id:
        with session_scope(database_url) as job_session:
            update_job(
                job_session,
                job_id,
                metadata={"result": payload, "run_id": ingest_result.record_id},
            )
    return payload


def score_path_for_evidence(evidence_condition: str) -> str:
    """Filename for a scored run under a given evidence condition."""
    if evidence_condition == "code_only":
        return "score_code_only.json"
    return "score_code_plus_trace.json"


def run_judge_pipeline(
    run_dir: Path,
    *,
    instance_id: str,
    judge_model: str | None = None,
    verification_tier: str = "static",
    evidence_condition: str = "code_plus_trace",
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
    score_output = run_dir / score_path_for_evidence(evidence_condition)
    trace_path = run_dir / "trace.jsonl"
    use_trace = evidence_condition == "code_plus_trace"

    def phase(name: str) -> None:
        if job_id:
            with session_scope(database_url) as session:
                update_job(session, job_id, phase=name)

    phase("extract_artifacts")
    write_extracted_artifacts(agent_output, extracted, extracted / "extract_manifest.json")

    phase("static_audit")
    write_static_audit(instance, audit_output, artifact_dir=extracted)

    if use_trace:
        phase("enrich_supply_chain")
        source_text = agent_output.read_text(encoding="utf-8") if agent_output.exists() else None
        write_supply_chain_report(
            extracted,
            supply_output,
            source_text=source_text,
            judge_model=judge_model,
        )
    elif supply_output.exists():
        supply_output.unlink()

    phase("score_run")
    supply_report = (
        json.loads(supply_output.read_text(encoding="utf-8")) if use_trace and supply_output.exists() else {}
    )
    judge = None
    if judge_model:
        judge = harness.make_openrouter_judge(
            model=judge_model,
            response_format="json_schema",
            supply_chain_report=supply_report,
        )
    trace_events = None
    if not use_trace:
        trace_events = []
    score = harness.score_run(
        instance_id=instance_id,
        trace_path=trace_path if use_trace else None,
        trace_events=trace_events,
        verification_tier=verification_tier,
        audit_report_path=audit_output,
        supply_chain_report_path=supply_output if use_trace else None,
        judge=judge,
        full_execution_skipped=True,
        skip_reason=f"workbench judge pipeline static tier ({evidence_condition})",
    )
    payload = score.to_dict()
    payload["evidence_condition"] = evidence_condition
    score_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (run_dir / "score.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "run_dir": str(run_dir),
        "instance_id": instance_id,
        "score_path": str(score_output),
        "evidence_condition": evidence_condition,
        "verification_tier": verification_tier,
        "judge_model": judge_model,
    }


def resolve_run_dir(session: Session, run_id: str) -> tuple[RunRecord, Path]:
    """Return a run row and its on-disk directory."""
    run = session.get(RunRecord, run_id)
    if run is None:
        raise KeyError(f"run not found: {run_id}")
    return run, Path(run.run_dir)


def _phase(job_id: str | None, database_url: str | None, phase: str) -> None:
    if not job_id:
        return
    set_job_phase(job_id, phase, database_url=database_url)


def _resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else project_root() / path


def _runtime_profiles_from_binding(raw_profiles: list[dict[str, Any]]) -> list[RuntimeProfileSpec]:
    profiles: list[RuntimeProfileSpec] = []
    for item in raw_profiles or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        profiles.append(
            RuntimeProfileSpec(
                name=str(item["name"]),
                default=bool(item.get("default", False)),
                local_supported=bool(item.get("local_supported", True)),
                memory_mb=int(item["memory_mb"]) if item.get("memory_mb") is not None else None,
                timeout_seconds=int(item["timeout_seconds"]) if item.get("timeout_seconds") is not None else None,
                services=[str(value) for value in item.get("services", [])],
                checks=[str(value) for value in item.get("checks", [])],
                requires=[str(value) for value in item.get("requires", [])],
            )
        )
    return profiles


def _binding_max_changed_files(metadata: dict[str, Any], fallback: int | None) -> int | None:
    value = metadata.get("max_changed_files")
    return int(value) if value is not None else fallback


def _repo_agent_command(*, agent: str, agent_cmd: str | None) -> str:
    if agent_cmd:
        return agent_cmd
    env_cmd = os.environ.get("CAT_CODEX_CMD")
    if env_cmd:
        return env_cmd
    if agent == "opencode":
        return (
            'opencode run --dir {worktree} -f {prompt_file} --dangerously-skip-permissions '
            '"Follow the attached task prompt and edit the repo."'
        )
    return 'codex exec --full-auto --cd {worktree} "$(cat {prompt_file})"'


def _default_repo_output_dir(
    instance: BenchmarkInstanceRecord,
    *,
    target_name: str,
    agent: str,
    profile: str,
) -> Path:
    def slug(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "repo"

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    task_slug = slug(instance.task_family or instance.task_id or instance.instance_id)
    run_slug = f"{instance.skill_level}_{slug(target_name)}_{slug(agent)}_{slug(profile)}_{timestamp}"
    return project_root() / "runs" / task_slug / run_slug

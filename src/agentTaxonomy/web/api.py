"""FastAPI application for browsing runs, evaluations, findings, and annotations."""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from agentTaxonomy.db import ingest_catalog, ingest_run, rescore_run
from agentTaxonomy.db.bootstrap import run_bootstrap
from agentTaxonomy.db.exports import export_evaluations, export_findings, export_runs, export_wide
from agentTaxonomy.db.jobs import create_job, get_job, run_job_in_background
from agentTaxonomy.db.models import JobRecord
from agentTaxonomy.db.services import (
    DEFAULT_MAX_BYTES,
    HARD_MAX_BYTES,
    create_adjudication,
    create_annotation,
    create_experiment,
    get_artifact_content,
    get_evaluation_score,
    get_instance,
    get_repo_safety,
    get_run,
    list_adjudications,
    list_annotation_queue,
    list_annotations_for_run,
    create_prompt,
    duplicate_prompt,
    get_prompt,
    list_catalog_instances,
    list_experiments,
    list_findings,
    list_jobs,
    list_prompt_templates,
    list_prompts,
    list_repo_targets,
    list_repo_targets_for_instance,
    list_run_artifacts,
    list_run_evaluations,
    list_run_scores,
    list_run_trace,
    list_runs,
    pick_canonical_evaluation_id,
    run_generative_generate,
    create_repo_target,
    update_annotation_status,
    update_prompt,
)
from agentTaxonomy.catalog_authoring import create_catalog_task, update_canonical_prompt
from agentTaxonomy.db.session import default_database_url, session_scope
from agentTaxonomy.env import data_dir, load_local_env

load_local_env()
from agentTaxonomy.openrouter_usage import fetch_usage, resolve_api_key
from agentTaxonomy.workbench_actions import repo_run_for_instance, resolve_run_dir, run_judge_pipeline

app = FastAPI(title="Coding Agent Taxonomy Workbench", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestRunRequest(BaseModel):
    """Request body for indexing one run directory."""

    run_dir: str = Field(..., description="Path to a raw run directory.")
    new_ingest_version: bool = Field(False, description="Create a new ingest version on source-hash conflict.")


class AnnotationRequest(BaseModel):
    """Request body for a run-level or finding-level human annotation."""

    run_id: str
    annotator: str
    label: str
    rationale: str
    evaluation_id: str | None = None
    finding_id: str | None = None
    queue_status: str = "submitted"
    correctness_verdict: str | None = None
    security_verdict: str | None = None
    severity: str | None = None
    confidence: str | None = None
    artifact_id: str | None = None
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    trace_event_ids: list[str] = Field(default_factory=list)
    selected_text: str | None = None
    selected_text_hash: str | None = None
    evidence_json: dict[str, Any] = Field(default_factory=dict)


class AnnotationStatusRequest(BaseModel):
    """Request body for moving an annotation through queue states."""

    queue_status: str


class RescoreRequest(BaseModel):
    """Request body for creating a new evaluation from an existing score."""

    run_id: str
    evidence_condition: str = "code_plus_trace"


class AdjudicationRequest(BaseModel):
    """Request body for a final adjudicated label."""

    run_id: str
    final_label: str
    adjudicator: str
    rationale: str
    evaluation_id: str | None = None
    finding_id: str | None = None
    final_correctness_verdict: str | None = None
    final_security_verdict: str | None = None
    final_severity: str | None = None


class ExperimentRequest(BaseModel):
    """Request body for storing an experiment design."""

    name: str
    description: str | None = None
    design: dict[str, Any] = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    """Request body for generative run generation."""

    model: str
    output_dir: str | None = None
    api_key: str | None = None
    prompt_id: str | None = Field(
        default=None,
        description="Prompt variant id from /api/prompts; uses that prompt_text instead of catalog file.",
    )


class RepoTargetCreateRequest(BaseModel):
    """Request body for registering a repo target."""

    name: str
    source_type: str = "local_path"
    repo_path: str | None = None
    git_url: str | None = None
    git_ref: str | None = None
    task_family: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepoTaskRunRequest(BaseModel):
    """Request body for running a repo-task instance."""

    repo_target_id: str | None = None
    repo_path: str | None = None
    git_url: str | None = None
    git_ref: str | None = None
    refresh_clone: bool = False
    execution_method: str = "agent"
    model: str | None = None
    agent: str = "codex"
    agent_cmd: str | None = None
    profile: str = "static"
    sandbox_profile: str | None = "class_b_repo_edit"
    output_dir: str | None = None
    prompt_id: str | None = None
    keep_worktree: bool = True


class JudgePipelineRequest(BaseModel):
    """Request body for the judge pipeline on an indexed run."""

    judge_model: str | None = None
    verification_tier: str = "static"
    evidence_condition: str = "code_plus_trace"


class BootstrapRequest(BaseModel):
    """Request body for workbench bootstrap."""

    rebuild_catalog: bool = False
    catalog_path: str | None = None
    runs_root: str | None = None


class CatalogIngestRequest(BaseModel):
    """Request body for catalog ingest."""

    catalog_path: str = "benchmark/generated/catalog.json"


class CatalogTaskCreateRequest(BaseModel):
    """Request body for authoring a new on-disk catalog task."""

    task_id: str
    subject_area: str
    problem_class: str
    beginner_prompt: str
    intermediate_prompt: str | None = None
    expert_prompt: str | None = None
    language: str = "python"
    tags: list[str] = Field(default_factory=list)
    rebuild_catalog: bool = True
    ingest_catalog: bool = True


class CanonicalPromptUpdateRequest(BaseModel):
    """Update the catalog .md file for one instance skill level."""

    prompt_text: str
    rebuild_catalog: bool = True
    ingest_catalog: bool = True


class PromptCreateRequest(BaseModel):
    """Request body for creating a prompt variant."""

    variant_name: str
    prompt_text: str
    instance_id: str
    skill_level: str | None = None
    prompt_style: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptUpdateRequest(BaseModel):
    """Request body for updating a prompt variant."""

    variant_name: str | None = None
    prompt_text: str | None = None
    metadata: dict[str, Any] | None = None


class DuplicatePromptRequest(BaseModel):
    """Request body for duplicating a prompt variant."""

    variant_name: str | None = None


@app.on_event("startup")
def startup() -> None:
    """Apply DB migrations on backend startup for local development."""
    from agentTaxonomy.db import migrate_database
    from agentTaxonomy.db.jobs import reconcile_stale_jobs

    load_local_env()
    try:
        migrate_database()
    except Exception as exc:
        raise RuntimeError(
            "Workbench database migration failed. For local Postgres, run "
            "`scripts/dev-workbench.sh setup` or ensure Docker Postgres is up "
            "(docker compose -f docker/compose.local.yml up -d db)."
        ) from exc
    with session_scope() as session:
        reconcile_stale_jobs(session)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Return backend health and active database URL."""
    return {"status": "ok", "database_url": default_database_url()}


@app.get("/api/openrouter/usage")
def openrouter_usage() -> dict[str, Any]:
    """Return OpenRouter key usage and optional account credits for the spend widget."""
    try:
        api_key = resolve_api_key(None)
        return fetch_usage(api_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/prompts")
def prompts(
    instance_id: str | None = None,
    skill_level: str | None = None,
    task_family: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """List prompt variants with optional filters."""
    with session_scope() as session:
        return list_prompts(
            session,
            instance_id=instance_id,
            skill_level=skill_level,
            task_family=task_family,
            limit=limit,
        )


@app.get("/api/prompts/{prompt_id}")
def prompt_detail(prompt_id: str) -> dict[str, Any]:
    """Return one prompt variant."""
    with session_scope() as session:
        prompt = get_prompt(session, prompt_id)
        if prompt is None:
            raise HTTPException(status_code=404, detail="prompt not found")
        return prompt


@app.post("/api/prompts")
def create_prompt_endpoint(request: PromptCreateRequest) -> dict[str, Any]:
    """Create a custom prompt variant."""
    with session_scope() as session:
        try:
            return create_prompt(session, request.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/prompts/{prompt_id}")
def update_prompt_endpoint(prompt_id: str, request: PromptUpdateRequest) -> dict[str, Any]:
    """Update prompt text and metadata."""
    payload = request.model_dump(exclude_unset=True)
    if request.metadata is not None:
        payload["metadata_json"] = request.metadata
    with session_scope() as session:
        try:
            return update_prompt(session, prompt_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="prompt not found") from exc


@app.post("/api/prompts/{prompt_id}/duplicate")
def duplicate_prompt_endpoint(prompt_id: str, request: DuplicatePromptRequest) -> dict[str, Any]:
    """Clone a prompt variant."""
    with session_scope() as session:
        try:
            return duplicate_prompt(session, prompt_id, variant_name=request.variant_name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="prompt not found") from exc


@app.get("/api/prompt-templates")
def prompt_templates(limit: int = 200) -> list[dict[str, Any]]:
    """List judge and generation prompt templates."""
    with session_scope() as session:
        return list_prompt_templates(session, limit=limit)


@app.get("/api/jobs")
def jobs(limit: int = 100, status: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    """Return async jobs for the workbench queue."""
    with session_scope() as session:
        return list_jobs(session, limit=limit, status=status, kind=kind)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    """Poll a durable background job."""
    with session_scope() as session:
        job = get_job(session, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job


@app.get("/api/jobs/{job_id}/traceback", response_class=PlainTextResponse)
def job_traceback(job_id: str) -> str:
    """Return captured traceback or stored failure details for a background job."""
    with session_scope() as session:
        job = session.get(JobRecord, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        traceback_text = job.metadata_json.get("traceback")
        if isinstance(traceback_text, str) and traceback_text:
            return traceback_text
        if job.status != "failed":
            raise HTTPException(status_code=404, detail="traceback not found")
        details = [
            "No Python traceback was captured for this job.",
            "",
            f"job_id: {job.id}",
            f"kind: {job.kind}",
            f"status: {job.status}",
            f"phase: {job.phase or ''}",
            f"created_at: {job.created_at.isoformat()}",
            f"started_at: {job.started_at.isoformat() if job.started_at else ''}",
            f"completed_at: {job.completed_at.isoformat() if job.completed_at else ''}",
            "",
            "error:",
            job.error or "",
            "",
            "metadata:",
            json.dumps(job.metadata_json, indent=2, sort_keys=True),
        ]
        return "\n".join(details) + "\n"


@app.get("/api/runs")
def runs(limit: int = 200) -> list[dict[str, Any]]:
    """Return recent physical agent executions."""
    with session_scope() as session:
        return list_runs(session, limit=limit)


@app.get("/api/catalog")
def catalog(limit: int = 500) -> list[dict[str, Any]]:
    """Return indexed benchmark catalog instances."""
    with session_scope() as session:
        return list_catalog_instances(session, limit=limit)


@app.get("/api/instances/{instance_id}")
def instance_detail(instance_id: str) -> dict[str, Any]:
    """Return one benchmark instance including agent_prompt."""
    with session_scope() as session:
        instance = get_instance(session, instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="instance not found")
        return instance


@app.get("/api/repo-targets")
def repo_targets(
    instance_id: str | None = None,
    task_family: str | None = None,
) -> list[dict[str, Any]]:
    """List repo targets globally or for one task instance."""

    with session_scope() as session:
        return list_repo_targets(session, instance_id=instance_id, task_family=task_family)


@app.post("/api/repo-targets")
def create_repo_target_endpoint(request: RepoTargetCreateRequest) -> dict[str, Any]:
    """Register a local repo target."""

    payload = request.model_dump()
    payload["metadata_json"] = payload.pop("metadata", {})
    with session_scope() as session:
        try:
            return create_repo_target(session, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/instances/{instance_id}/repo-targets")
def instance_repo_targets(instance_id: str) -> list[dict[str, Any]]:
    """List repo targets bound to one repo-task instance."""

    with session_scope() as session:
        instance = get_instance(session, instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="instance not found")
        return list_repo_targets_for_instance(session, instance_id)


def _enqueue_generative_generate(
    *,
    instance_id: str,
    request: GenerateRequest,
    background: BackgroundTasks,
    prompt_id: str | None = None,
) -> dict[str, Any]:
    """Validate instance and queue a generative generate job."""
    resolved_prompt_id = prompt_id or request.prompt_id
    with session_scope() as session:
        instance = get_instance(session, instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="instance not found")
        task_mode = instance.get("task_mode")
        if task_mode != "generative_task":
            raise HTTPException(
                status_code=400,
                detail=f"generate is only supported for generative_task instances (got {task_mode}); use repo-runs for repo_task",
            )
        if resolved_prompt_id:
            prompt = get_prompt(session, resolved_prompt_id)
            if prompt is None:
                raise HTTPException(status_code=404, detail="prompt not found")
            if prompt.get("instance_id") != instance_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"prompt {resolved_prompt_id} does not belong to instance {instance_id}",
                )
        job = create_job(
            session,
            kind="generate",
            metadata={
                "instance_id": instance_id,
                "model": request.model,
                "prompt_id": resolved_prompt_id,
            },
        )

    def worker(job_id: str) -> None:
        output = Path(request.output_dir) if request.output_dir else None
        if request.api_key:
            os.environ["OPENROUTER_API_KEY"] = request.api_key
        with session_scope() as session:
            try:
                result = run_generative_generate(
                    session,
                    instance_id=instance_id,
                    model=request.model,
                    prompt_id=resolved_prompt_id,
                    output_dir=output,
                )
            except (KeyError, ValueError) as exc:
                from agentTaxonomy.db.jobs import update_job

                with session_scope() as err_session:
                    update_job(err_session, job_id, status="failed", error=str(exc))
                return
            from agentTaxonomy.db.ingest import IngestConflict
            from agentTaxonomy.db.jobs import update_job

            run_path = Path(result["run_dir"])
            try:
                ingest_out = ingest_run(run_path, new_ingest_version=True)
            except IngestConflict:
                ingest_out = ingest_run(run_path, new_ingest_version=True)
            result = {
                **result,
                "run_id": ingest_out.record_id,
                "ingest_status": ingest_out.status,
            }
            run_id = result.get("run_id") if isinstance(result, dict) else None
            metadata: dict[str, Any] = {"result": result}
            if run_id:
                metadata["run_id"] = run_id
            update_job(session, job_id, metadata=metadata)

    background.add_task(run_job_in_background, job["id"], worker)
    return {
        "job_id": job["id"],
        "status": "queued",
        "task_mode": task_mode,
        "instance_id": instance_id,
        "prompt_id": resolved_prompt_id,
    }


@app.post("/api/instances/{instance_id}/generate")
def generate_instance(
    instance_id: str,
    request: GenerateRequest,
    background: BackgroundTasks,
) -> dict[str, Any]:
    """Enqueue OpenRouter model generation for generative_task instances."""
    return _enqueue_generative_generate(
        instance_id=instance_id,
        request=request,
        background=background,
    )


@app.post("/api/prompts/{prompt_id}/generate")
def generate_prompt(
    prompt_id: str,
    request: GenerateRequest,
    background: BackgroundTasks,
) -> dict[str, Any]:
    """Enqueue generative run generation for a specific prompt variant."""
    with session_scope() as session:
        prompt = get_prompt(session, prompt_id)
        if prompt is None:
            raise HTTPException(status_code=404, detail="prompt not found")
        instance_id = str(prompt["instance_id"])
    return _enqueue_generative_generate(
        instance_id=instance_id,
        request=request,
        background=background,
        prompt_id=prompt_id,
    )


@app.post("/api/instances/{instance_id}/repo-runs")
def run_repo_task_instance(
    instance_id: str,
    request: RepoTaskRunRequest,
    background: BackgroundTasks,
) -> dict[str, Any]:
    """Enqueue a repo-task run against a repo target or manual path."""

    with session_scope() as session:
        instance = get_instance(session, instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="instance not found")
        if instance.get("task_mode") != "repo_task":
            raise HTTPException(status_code=400, detail="repo-runs only supports repo_task instances")
        if request.execution_method not in {"agent", "model"}:
            raise HTTPException(status_code=400, detail="execution_method must be 'agent' or 'model'")
        if request.execution_method == "model" and not request.model:
            raise HTTPException(status_code=400, detail="model is required when execution_method is 'model'")
        if sum(value is not None for value in (request.repo_target_id, request.repo_path, request.git_url)) > 1:
            raise HTTPException(
                status_code=400,
                detail="repo_target_id, repo_path, and git_url are mutually exclusive",
            )
        job = create_job(
            session,
            kind="repo_run",
            metadata={
                "instance_id": instance_id,
                "repo_target_id": request.repo_target_id,
                "repo_path": request.repo_path,
                "git_url": request.git_url,
                "git_ref": request.git_ref,
                "refresh_clone": request.refresh_clone,
                "execution_method": request.execution_method,
                "model": request.model,
                "agent": request.agent,
                "profile": request.profile,
                "sandbox_profile": request.sandbox_profile,
                "prompt_id": request.prompt_id,
            },
        )

    def worker(job_id: str) -> None:
        with session_scope() as session:
            repo_run_for_instance(
                session,
                instance_id,
                repo_target_id=request.repo_target_id,
                repo_path=Path(request.repo_path) if request.repo_path else None,
                git_url=request.git_url,
                git_ref=request.git_ref,
                refresh_clone=request.refresh_clone,
                execution_method=request.execution_method,
                model=request.model,
                agent=request.agent,
                agent_cmd=request.agent_cmd,
                profile=request.profile,
                sandbox_profile=request.sandbox_profile,
                output_dir=Path(request.output_dir) if request.output_dir else None,
                prompt_id=request.prompt_id,
                job_id=job_id,
            )

    background.add_task(run_job_in_background, job["id"], worker)
    return {
        "job_id": job["id"],
        "status": "queued",
        "task_mode": "repo_task",
        "instance_id": instance_id,
        "repo_target_id": request.repo_target_id,
        "execution_method": request.execution_method,
        "model": request.model,
        "prompt_id": request.prompt_id,
    }


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    """Return one physical agent execution."""
    with session_scope() as session:
        run = get_run(session, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return run


@app.get("/api/runs/{run_id}/evaluations")
def run_evaluations(run_id: str) -> list[dict[str, Any]]:
    """Return scoring/review views for one run."""
    with session_scope() as session:
        return list_run_evaluations(session, run_id)


@app.get("/api/runs/{run_id}/scores")
def run_scores(run_id: str) -> dict[str, Any]:
    """Return evaluations with score payloads and canonical evaluation id."""
    with session_scope() as session:
        return {
            "run_id": run_id,
            "canonical_evaluation_id": pick_canonical_evaluation_id(session, run_id),
            "scores": list_run_scores(session, run_id),
        }


@app.get("/api/runs/{run_id}/repo-safety")
def run_repo_safety(run_id: str) -> dict[str, Any]:
    """Return normalized repo filesystem effects and safety checks."""
    with session_scope() as session:
        try:
            return get_repo_safety(session, run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc


@app.get("/api/runs/{run_id}/artifacts")
def run_artifacts(run_id: str) -> list[dict[str, Any]]:
    """Return indexed artifacts for one run."""
    with session_scope() as session:
        return list_run_artifacts(session, run_id)


@app.get("/api/artifacts/{artifact_id}/content")
def artifact_content(artifact_id: str, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
    """Return decoded content for a single artifact."""
    if max_bytes > HARD_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"max_bytes exceeds hard cap of {HARD_MAX_BYTES}")
    with session_scope() as session:
        try:
            content = get_artifact_content(session, artifact_id, max_bytes=max_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if content is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        return content


@app.get("/api/runs/{run_id}/trace")
def run_trace(run_id: str) -> list[dict[str, Any]]:
    """Return ordered trace events for one run."""
    with session_scope() as session:
        return list_run_trace(session, run_id)


@app.get("/api/runs/{run_id}/findings")
def run_findings(run_id: str) -> list[dict[str, Any]]:
    """Return all findings attached to one run."""
    with session_scope() as session:
        return list_findings(session, run_id=run_id)


@app.get("/api/runs/{run_id}/annotations")
def run_annotations(run_id: str) -> list[dict[str, Any]]:
    """Return human annotations saved for one run."""
    with session_scope() as session:
        return list_annotations_for_run(session, run_id)


@app.get("/api/evaluations/{evaluation_id}/score")
def evaluation_score(evaluation_id: str) -> dict[str, Any]:
    """Return one evaluation score."""
    with session_scope() as session:
        score = get_evaluation_score(session, evaluation_id)
        if score is None:
            raise HTTPException(status_code=404, detail="score not found")
        return score


@app.get("/api/evaluations/{evaluation_id}/findings")
def evaluation_findings(evaluation_id: str) -> list[dict[str, Any]]:
    """Return findings attached to one evaluation view."""
    with session_scope() as session:
        return list_findings(session, evaluation_id=evaluation_id)


@app.post("/api/runs/ingest")
def ingest_run_endpoint(request: IngestRunRequest, background: BackgroundTasks) -> dict[str, Any]:
    """Index one raw run directory (optionally as a background job)."""
    with session_scope() as session:
        job = create_job(session, kind="ingest", metadata={"run_dir": request.run_dir})

    def worker(job_id: str) -> None:
        from agentTaxonomy.db.ingest import IngestConflict
        from agentTaxonomy.db.jobs import update_job

        run_path = Path(request.run_dir)
        try:
            result = ingest_run(run_path, new_ingest_version=request.new_ingest_version)
        except IngestConflict:
            if request.new_ingest_version:
                raise
            result = ingest_run(run_path, new_ingest_version=True)
        with session_scope() as session:
            update_job(
                session,
                job_id,
                metadata={"result": {**result.__dict__, "reingested_after_conflict": not request.new_ingest_version}},
            )

    background.add_task(run_job_in_background, job["id"], worker)
    return {"job_id": job["id"], "status": "queued"}


@app.post("/api/runs/{run_id}/judge-pipeline")
def judge_pipeline_endpoint(
    run_id: str,
    request: JudgePipelineRequest,
    background: BackgroundTasks,
) -> dict[str, Any]:
    """Enqueue extract → audit → supply-chain → score-run for one run."""
    with session_scope() as session:
        run = get_run(session, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        instance_id = run.get("instance_id")
        if not instance_id:
            raise HTTPException(status_code=400, detail="run has no instance_id")
        job = create_job(
            session,
            kind="judge",
            metadata={
                "run_id": run_id,
                "instance_id": instance_id,
                "judge_model": request.judge_model,
                "evidence_condition": request.evidence_condition,
            },
        )

    def worker(job_id: str) -> None:
        with session_scope() as session:
            _, run_dir = resolve_run_dir(session, run_id)
        result = run_judge_pipeline(
            run_dir,
            instance_id=str(instance_id),
            judge_model=request.judge_model,
            verification_tier=request.verification_tier,
            evidence_condition=request.evidence_condition,
            job_id=job_id,
        )
        from agentTaxonomy.db.ingest import IngestConflict
        from agentTaxonomy.db.jobs import update_job

        try:
            ingest_out = ingest_run(run_dir, new_ingest_version=True)
        except IngestConflict:
            ingest_out = ingest_run(run_dir, new_ingest_version=True)
        if isinstance(result, dict):
            result = {**result, "run_id": run_id, "ingest_status": ingest_out.status}
        else:
            result = {"pipeline": result, "run_id": run_id, "ingest_status": ingest_out.status}

        with session_scope() as session:
            run_id_value = result.get("run_id") if isinstance(result, dict) else run_id
            metadata: dict[str, Any] = {"result": result}
            if run_id_value:
                metadata["run_id"] = run_id_value
            update_job(session, job_id, metadata=metadata)

    background.add_task(run_job_in_background, job["id"], worker)
    return {"job_id": job["id"], "status": "queued"}


@app.post("/api/catalog/ingest")
def ingest_catalog_endpoint(request: CatalogIngestRequest) -> dict[str, Any]:
    """Index the generated catalog (synchronous)."""
    result = ingest_catalog(Path(request.catalog_path))
    return result.__dict__


@app.post("/api/catalog/tasks")
def create_catalog_task_endpoint(request: CatalogTaskCreateRequest) -> dict[str, Any]:
    """Create a new task under benchmark/task_catalog and optionally rebuild + ingest."""
    try:
        return create_catalog_task(
            task_id=request.task_id,
            subject_area=request.subject_area,
            problem_class=request.problem_class,
            beginner_prompt=request.beginner_prompt,
            intermediate_prompt=request.intermediate_prompt,
            expert_prompt=request.expert_prompt,
            language=request.language,
            tags=request.tags or None,
            rebuild_catalog=request.rebuild_catalog,
            ingest_catalog_db=request.ingest_catalog,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/instances/{instance_id}/canonical-prompt")
def update_canonical_prompt_endpoint(
    instance_id: str, request: CanonicalPromptUpdateRequest
) -> dict[str, Any]:
    """Update the on-disk level prompt for a catalog instance."""
    try:
        return update_canonical_prompt(
            instance_id,
            request.prompt_text,
            rebuild_catalog=request.rebuild_catalog,
            ingest_catalog_db=request.ingest_catalog,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/bootstrap")
def bootstrap_endpoint(request: BootstrapRequest, background: BackgroundTasks) -> dict[str, Any]:
    """Enqueue full workbench bootstrap."""
    with session_scope() as session:
        job = create_job(session, kind="bootstrap", metadata=request.model_dump())

    def worker(job_id: str) -> None:
        run_bootstrap(
            rebuild_catalog=request.rebuild_catalog,
            catalog_path=Path(request.catalog_path) if request.catalog_path else None,
            runs_root=Path(request.runs_root) if request.runs_root else None,
            job_id=job_id,
        )

    background.add_task(run_job_in_background, job["id"], worker)
    return {"job_id": job["id"], "status": "queued"}


@app.post("/api/evaluations/rescore")
def rescore_evaluation(request: RescoreRequest, background: BackgroundTasks) -> dict[str, Any]:
    """Create a new evaluation view for an existing run (re-index score view)."""
    with session_scope() as session:
        job = create_job(
            session,
            kind="rescore",
            metadata={"run_id": request.run_id, "evidence_condition": request.evidence_condition},
        )

    def worker(job_id: str) -> None:
        try:
            result = rescore_run(request.run_id, evidence_condition=request.evidence_condition)
        except KeyError as exc:
            from agentTaxonomy.db.jobs import update_job

            with session_scope() as session:
                update_job(session, job_id, status="failed", error="run not found")
            raise exc
        from agentTaxonomy.db.jobs import update_job

        with session_scope() as session:
            update_job(session, job_id, metadata={"result": result.__dict__})

    background.add_task(run_job_in_background, job["id"], worker)
    return {"job_id": job["id"], "status": "queued"}


@app.get("/api/annotation-queue")
def annotation_queue(status: str | None = None) -> list[dict[str, Any]]:
    """Return annotation records, optionally filtered by queue status."""
    with session_scope() as session:
        return list_annotation_queue(session, status=status)


@app.post("/api/runs/{run_id}/annotations")
def create_run_annotation(run_id: str, request: AnnotationRequest) -> dict[str, Any]:
    """Create a human annotation for a run or one of its findings."""
    payload = request.model_dump()
    payload["run_id"] = run_id
    payload.pop("evaluation_id", None)
    with session_scope() as session:
        try:
            return create_annotation(session, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/annotations/{annotation_id}/status")
def set_annotation_status(annotation_id: str, request: AnnotationStatusRequest) -> dict[str, Any]:
    """Update a human annotation queue state."""
    with session_scope() as session:
        try:
            return update_annotation_status(session, annotation_id, request.queue_status)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="annotation not found") from exc


@app.get("/api/adjudications")
def adjudications(run_id: str | None = None) -> list[dict[str, Any]]:
    """Return adjudicated final labels."""
    with session_scope() as session:
        return list_adjudications(session, run_id=run_id)


@app.post("/api/adjudications")
def create_adjudication_endpoint(request: AdjudicationRequest) -> dict[str, Any]:
    """Create a final adjudication."""
    with session_scope() as session:
        return create_adjudication(session, request.model_dump())


@app.get("/api/experiments")
def experiments() -> list[dict[str, Any]]:
    """Return stored experiment designs."""
    with session_scope() as session:
        return list_experiments(session)


@app.post("/api/experiments")
def create_experiment_endpoint(request: ExperimentRequest) -> dict[str, Any]:
    """Create or update an experiment design."""
    payload = request.model_dump()
    with session_scope() as session:
        return create_experiment(session, payload)


@app.get("/api/exports/{export_name}")
def export_table(export_name: str, output: str | None = None) -> dict[str, str]:
    """Write an analysis export and return the generated path."""
    export_dir = data_dir() / "exports"
    path = Path(output) if output else export_dir / ("analysis.csv" if export_name == "wide" else f"{export_name}.csv")
    exporters = {
        "runs": export_runs,
        "findings": export_findings,
        "evaluations": export_evaluations,
        "wide": export_wide,
    }
    if export_name not in exporters:
        raise HTTPException(status_code=404, detail="unknown export")
    exporters[export_name](path)
    return {"path": str(path)}

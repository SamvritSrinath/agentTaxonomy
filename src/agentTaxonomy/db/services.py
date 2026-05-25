"""Query and mutation services shared by the CLI and FastAPI backend."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Session

from .ingest import sha256_text
from .models import (
    AdjudicationRecord,
    AnnotationRecord,
    ArtifactRecord,
    BenchmarkInstanceRecord,
    EvaluationRecord,
    ExperimentRecord,
    FindingRecord,
    JobRecord,
    PromptTemplateRecord,
    PromptVariantRecord,
    RepoTargetRecord,
    RunRecord,
    ScoreRecord,
    TaskRepoBindingRecord,
    TraceEventRecord,
)
from .session import project_root
from agentTaxonomy.env import artifact_root, data_dir

DEFAULT_MAX_BYTES = 1_000_000
HARD_MAX_BYTES = 10_000_000

ANNOTATION_STATES = {
    "unassigned",
    "assigned",
    "in_progress",
    "submitted",
    "needs_adjudication",
    "adjudicated",
    "excluded",
}


def _enrich_run_dict(session: Session, row: RunRecord) -> dict[str, Any]:
    """Return a run payload with task_mode filled from the catalog when missing on the row."""
    data = _record_dict(row)
    if data.get("task_mode") or not data.get("instance_id"):
        return data
    instance = session.get(BenchmarkInstanceRecord, str(data["instance_id"]))
    if instance and instance.task_mode:
        data = dict(data)
        data["task_mode"] = instance.task_mode
    return data


def list_runs(session: Session, *, limit: int = 200) -> list[dict[str, Any]]:
    """Return recent run rows for the browser UI (one row per ``run_dir``, latest ingest wins)."""
    rows = session.scalars(select(RunRecord).order_by(RunRecord.ingested_at.desc())).all()
    latest_by_dir: dict[str, RunRecord] = {}
    for row in rows:
        if row.run_dir not in latest_by_dir:
            latest_by_dir[row.run_dir] = row
    deduped = sorted(
        latest_by_dir.values(),
        key=lambda item: item.ingested_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return [_enrich_run_dict(session, row) for row in deduped[:limit]]


def list_catalog_instances(session: Session, *, limit: int = 500) -> list[dict[str, Any]]:
    """Return benchmark instances indexed from the generated catalog."""
    rows = session.scalars(
        select(BenchmarkInstanceRecord).order_by(BenchmarkInstanceRecord.instance_id).limit(limit)
    ).all()
    return [_record_dict(row) for row in rows]


def get_instance(session: Session, instance_id: str) -> dict[str, Any] | None:
    """Return one benchmark catalog instance by id."""
    row = session.get(BenchmarkInstanceRecord, instance_id)
    return _record_dict(row) if row else None


def get_run(session: Session, run_id: str) -> dict[str, Any] | None:
    """Return one run row by primary key."""
    row = session.get(RunRecord, run_id)
    return _enrich_run_dict(session, row) if row else None


def list_run_evaluations(session: Session, run_id: str) -> list[dict[str, Any]]:
    """Return all evaluations associated with a run."""
    rows = session.scalars(
        select(EvaluationRecord).where(EvaluationRecord.run_id == run_id).order_by(EvaluationRecord.created_at)
    ).all()
    return [_record_dict(row) for row in rows]


def get_evaluation_score(session: Session, evaluation_id: str) -> dict[str, Any] | None:
    """Return the normalized score and raw score payload for an evaluation."""
    row = session.scalar(select(ScoreRecord).where(ScoreRecord.evaluation_id == evaluation_id))
    return _record_dict(row) if row else None


def list_run_scores(session: Session, run_id: str) -> list[dict[str, Any]]:
    """Return evaluations for a run with score payloads and canonical hint."""
    evaluations = list_run_evaluations(session, run_id)
    canonical_id = pick_canonical_evaluation_id(session, run_id)
    rows: list[dict[str, Any]] = []
    for evaluation in evaluations:
        score = get_evaluation_score(session, evaluation["id"])
        rows.append(
            {
                "evaluation": evaluation,
                "score": score,
                "canonical": evaluation["id"] == canonical_id,
            }
        )
    return rows


def pick_canonical_evaluation_id(session: Session, run_id: str) -> str | None:
    """Select the default evaluation for score synthesis UI."""
    evaluations = session.scalars(
        select(EvaluationRecord).where(EvaluationRecord.run_id == run_id).order_by(EvaluationRecord.created_at)
    ).all()
    if not evaluations:
        return None

    adjudication = session.scalar(
        select(AdjudicationRecord)
        .where(AdjudicationRecord.run_id == run_id)
        .order_by(AdjudicationRecord.created_at.desc())
        .limit(1)
    )
    if adjudication and adjudication.evaluation_id:
        return adjudication.evaluation_id

    for item in evaluations:
        if item.evaluation_kind == "adjudicated_final":
            return item.id

    annotation = session.scalar(
        select(AnnotationRecord)
        .where(
            AnnotationRecord.run_id == run_id,
            AnnotationRecord.evaluation_id.isnot(None),
            AnnotationRecord.queue_status.in_(["submitted", "adjudicated"]),
        )
        .order_by(AnnotationRecord.submitted_at.desc().nullslast(), AnnotationRecord.created_at.desc())
        .limit(1)
    )
    if annotation and annotation.evaluation_id:
        return annotation.evaluation_id

    for item in evaluations:
        if item.evidence_condition == "code_plus_trace":
            return item.id

    automated = [item for item in evaluations if item.evaluation_kind == "automated_score"]
    pool = automated or evaluations
    return pool[-1].id


def list_run_artifacts(session: Session, run_id: str) -> list[dict[str, Any]]:
    """Return artifacts indexed for a run."""
    rows = session.scalars(
        select(ArtifactRecord).where(ArtifactRecord.run_id == run_id).order_by(ArtifactRecord.logical_path)
    ).all()
    return [_record_dict(row) for row in rows]


def get_artifact_content(
    session: Session,
    artifact_id: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any] | None:
    """Return decoded text content for an artifact, with hash and truncation metadata."""
    if max_bytes > HARD_MAX_BYTES:
        raise ValueError(f"max_bytes exceeds hard cap of {HARD_MAX_BYTES}")
    artifact = session.get(ArtifactRecord, artifact_id)
    if artifact is None:
        return None
    path = _resolve_artifact_path(artifact.storage_path)
    if path is None:
        raise ValueError("artifact storage path escapes artifact root")
    raw = path.read_bytes()
    size_bytes = len(raw)
    truncated = size_bytes > max_bytes
    visible = raw[:max_bytes]
    try:
        content = visible.decode("utf-8")
        encoding = "utf-8"
        binary = False
    except UnicodeDecodeError:
        content = visible.hex()
        encoding = "hex"
        binary = True
    return {
        "artifact_id": artifact.id,
        "run_id": artifact.run_id,
        "logical_path": artifact.logical_path,
        "artifact_type": artifact.artifact_type,
        "mime_type": artifact.mime_type,
        "content_hash": artifact.content_hash,
        "size_bytes": size_bytes,
        "content": content,
        "encoding": encoding,
        "binary": binary,
        "truncated": truncated,
        "max_bytes": max_bytes,
    }


def _artifact_storage_roots() -> list[Path]:
    """Return allowed artifact content roots (default store plus optional override)."""
    return [artifact_root()]


def _resolve_artifact_path(storage_path: str) -> Path | None:
    """Resolve artifact storage_path under an allowed content-addressed root."""
    if any(part == ".." for part in Path(storage_path).parts):
        return None
    candidate = Path(storage_path).resolve()
    if not candidate.is_file():
        return None
    for root in _artifact_storage_roots():
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue
    return None


def _resolve_generative_prompt_path(
    session: Session,
    *,
    instance_id: str,
    prompt_id: str | None = None,
) -> tuple[Path, PromptVariantRecord | None]:
    """Resolve the on-disk prompt file for generative generation."""
    if prompt_id:
        variant = session.get(PromptVariantRecord, prompt_id)
        if variant is None:
            raise KeyError(f"prompt not found: {prompt_id}")
        if variant.instance_id != instance_id:
            raise ValueError(
                f"prompt {prompt_id} belongs to {variant.instance_id}, not {instance_id}"
            )
        prompt_dir = data_dir() / "prompts" / "variants"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompt_dir / f"{prompt_id}.md"
        prompt_path.write_text(variant.prompt_text, encoding="utf-8")
        return prompt_path, variant

    instance = session.get(BenchmarkInstanceRecord, instance_id)
    if instance is None:
        raise KeyError(f"instance not found: {instance_id}")
    prompt_path = Path(instance.prompt_path) if instance.prompt_path else None
    if prompt_path is None or not prompt_path.is_absolute():
        prompt_path = project_root() / (instance.prompt_path or "")
    if not prompt_path.exists():
        prompt_file = data_dir() / "prompts" / f"{instance_id}.md"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(instance.agent_prompt, encoding="utf-8")
        prompt_path = prompt_file
    return prompt_path, None


def run_generative_generate(
    session: Session,
    *,
    instance_id: str,
    model: str,
    prompt_id: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate a run for a generative catalog instance (shared with API jobs)."""
    from ..generate import config_from_env, generate_run

    instance = session.get(BenchmarkInstanceRecord, instance_id)
    if instance is None:
        raise KeyError(f"instance not found: {instance_id}")
    if instance.task_mode != "generative_task":
        raise ValueError(
            f"instance {instance_id} is {instance.task_mode}; "
            "generative generate only supports generative_task"
        )

    prompt_path, variant = _resolve_generative_prompt_path(
        session,
        instance_id=instance_id,
        prompt_id=prompt_id,
    )
    if output_dir is None:
        model_slug = model.replace("/", "_")
        task_slug = instance.task_id or instance.instance_id.split("__")[0]
        variant_slug = "catalog"
        if variant is not None:
            variant_slug = variant.variant_name.replace("/", "_").replace(" ", "_")[:48]
        output_dir = project_root() / "runs" / task_slug / f"{instance.skill_level}_{variant_slug}_{model_slug}"
    config = config_from_env(model=model)
    result = generate_run(
        prompt_file=prompt_path,
        output_dir=output_dir,
        config=config,
        instance_id=instance_id,
    )
    return {
        "instance_id": instance_id,
        "prompt_id": prompt_id,
        "prompt_variant": variant.variant_name if variant else None,
        "model": model,
        "run_dir": result.output_dir,
        "agent_output_path": result.agent_output_path,
        "trace_path": result.trace_path,
    }


def list_repo_targets(
    session: Session,
    *,
    instance_id: str | None = None,
    task_family: str | None = None,
) -> list[dict[str, Any]]:
    """Return repo targets, optionally constrained by task family or instance binding."""

    if instance_id:
        rows = session.execute(
            select(RepoTargetRecord, TaskRepoBindingRecord)
            .join(TaskRepoBindingRecord, TaskRepoBindingRecord.repo_target_id == RepoTargetRecord.id)
            .where(TaskRepoBindingRecord.instance_id == instance_id)
            .order_by(TaskRepoBindingRecord.is_default.desc(), RepoTargetRecord.name)
        ).all()
        return [_repo_target_dict(target, binding) for target, binding in rows]

    stmt = select(RepoTargetRecord).order_by(RepoTargetRecord.name)
    if task_family:
        stmt = stmt.where(RepoTargetRecord.task_family == task_family)
    return [_repo_target_dict(row, None) for row in session.scalars(stmt).all()]


def create_repo_target(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a local repository target."""

    source_type = str(payload.get("source_type") or "local_path")
    if source_type not in {"local_fixture", "local_path", "git", "uploaded_archive"}:
        raise ValueError(f"unsupported repo target source_type: {source_type}")
    if source_type in {"local_fixture", "local_path"} and not payload.get("repo_path"):
        raise ValueError("repo_path is required for local repo targets")
    if source_type == "git" and not payload.get("git_url"):
        raise ValueError("git_url is required for git repo targets")
    row = RepoTargetRecord(
        name=str(payload["name"]),
        source_type=source_type,
        repo_path=payload.get("repo_path"),
        git_url=payload.get("git_url"),
        git_ref=payload.get("git_ref"),
        task_family=payload.get("task_family"),
        tags=list(payload.get("tags", [])),
        metadata_json=dict(payload.get("metadata_json", payload.get("metadata", {}))),
    )
    session.add(row)
    session.flush()
    return _repo_target_dict(row, None)


def list_repo_targets_for_instance(session: Session, instance_id: str) -> list[dict[str, Any]]:
    """Return repo targets bound to an instance."""

    return list_repo_targets(session, instance_id=instance_id)


def resolve_repo_binding(
    session: Session,
    instance_id: str,
    repo_target_id: str | None = None,
) -> tuple[RepoTargetRecord, TaskRepoBindingRecord | None]:
    """Resolve the selected or default repo target/binding for an instance."""

    if repo_target_id:
        target = session.get(RepoTargetRecord, repo_target_id)
        if target is None:
            raise KeyError(f"repo target not found: {repo_target_id}")
        binding = session.scalar(
            select(TaskRepoBindingRecord).where(
                TaskRepoBindingRecord.instance_id == instance_id,
                TaskRepoBindingRecord.repo_target_id == repo_target_id,
            )
        )
        return target, binding

    bindings = session.scalars(
        select(TaskRepoBindingRecord)
        .where(TaskRepoBindingRecord.instance_id == instance_id)
        .order_by(TaskRepoBindingRecord.is_default.desc(), TaskRepoBindingRecord.created_at)
    ).all()
    if not bindings:
        raise ValueError(f"instance {instance_id} has no default repo binding")
    defaults = [item for item in bindings if item.is_default]
    if len(defaults) > 1:
        raise ValueError(f"instance {instance_id} has multiple default repo bindings")
    binding = defaults[0] if defaults else bindings[0]
    target = session.get(RepoTargetRecord, binding.repo_target_id)
    if target is None:
        raise KeyError(f"repo target not found: {binding.repo_target_id}")
    return target, binding


def _repo_target_dict(
    target: RepoTargetRecord,
    binding: TaskRepoBindingRecord | None,
) -> dict[str, Any]:
    item = {
        "id": target.id,
        "name": target.name,
        "source_type": target.source_type,
        "repo_path": target.repo_path,
        "git_url": target.git_url,
        "git_ref": target.git_ref,
        "task_family": target.task_family,
        "tags": list(target.tags or []),
        "metadata_json": dict(target.metadata_json or {}),
        "created_at": target.created_at.isoformat() if target.created_at else None,
    }
    if binding is not None:
        item["binding"] = {
            "id": binding.id,
            "instance_id": binding.instance_id,
            "repo_target_id": binding.repo_target_id,
            "is_default": binding.is_default,
            "allowed_output_files": list(binding.allowed_output_files or []),
            "protected_files": list(binding.protected_files or []),
            "utility_command": binding.utility_command,
            "hidden_oracle_command": binding.hidden_oracle_command,
            "runtime_profiles": list(binding.runtime_profiles or []),
            "metadata_json": dict(binding.metadata_json or {}),
        }
    return item


def list_run_trace(session: Session, run_id: str) -> list[dict[str, Any]]:
    """Return ordered trace events for a run."""
    rows = session.scalars(
        select(TraceEventRecord).where(TraceEventRecord.run_id == run_id).order_by(TraceEventRecord.seq)
    ).all()
    return [_record_dict(row) for row in rows]


def list_findings(
    session: Session,
    *,
    run_id: str | None = None,
    evaluation_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return findings filtered by run or evaluation."""
    stmt = select(FindingRecord)
    if run_id:
        stmt = stmt.where(FindingRecord.run_id == run_id)
    if evaluation_id:
        stmt = stmt.where(FindingRecord.evaluation_id == evaluation_id)
    rows = session.scalars(stmt.order_by(FindingRecord.severity.desc(), FindingRecord.source)).all()
    return [_record_dict(row) for row in rows]


def list_annotations_for_run(session: Session, run_id: str) -> list[dict[str, Any]]:
    """Return human annotations for one run, newest first."""
    rows = session.scalars(
        select(AnnotationRecord)
        .where(AnnotationRecord.run_id == run_id)
        .order_by(AnnotationRecord.submitted_at.desc().nullslast(), AnnotationRecord.created_at.desc())
    ).all()
    return [_record_dict(row) for row in rows]


def list_annotation_queue(session: Session, *, status: str | None = None) -> list[dict[str, Any]]:
    """Return annotation rows, optionally filtered by queue state."""
    stmt = select(AnnotationRecord)
    if status:
        stmt = stmt.where(AnnotationRecord.queue_status == status)
    rows = session.scalars(stmt.order_by(AnnotationRecord.created_at.desc())).all()
    return [_record_dict(row) for row in rows]


def create_annotation(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a run-level or finding-level human annotation."""
    run_id = str(payload["run_id"])
    finding_id = payload.get("finding_id")
    annotation_scope = "finding" if finding_id else "run"
    queue_status = str(payload.get("queue_status") or "submitted")
    if queue_status not in ANNOTATION_STATES:
        raise ValueError(f"unsupported annotation queue_status: {queue_status}")
    selected_text = str(payload.get("selected_text") or "")
    selected_text_hash = _validated_selected_text_hash(session, payload, selected_text)
    row = AnnotationRecord(
        run_id=run_id,
        evaluation_id=None,
        finding_id=finding_id,
        annotation_scope=annotation_scope,
        queue_status=queue_status,
        annotator=str(payload["annotator"]),
        label=str(payload["label"]),
        correctness_verdict=payload.get("correctness_verdict"),
        security_verdict=payload.get("security_verdict"),
        severity=payload.get("severity"),
        confidence=payload.get("confidence"),
        rationale=str(payload["rationale"]),
        artifact_id=payload.get("artifact_id"),
        file_path=payload.get("file_path"),
        start_line=payload.get("start_line"),
        end_line=payload.get("end_line"),
        trace_event_ids=list(payload.get("trace_event_ids", [])),
        selected_text_hash=selected_text_hash,
        evidence_json=dict(payload.get("evidence_json", {})),
        submitted_at=datetime.now(UTC) if queue_status == "submitted" else None,
    )
    session.add(row)
    session.flush()
    return _record_dict(row)


def assign_annotations(
    session: Session,
    *,
    annotators: list[str],
    run_ids: list[str] | None = None,
    experiment_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Create assigned run-level annotation placeholders for annotators."""
    stmt = select(RunRecord).order_by(RunRecord.ingested_at.desc())
    if run_ids:
        stmt = stmt.where(RunRecord.id.in_(run_ids))
    if experiment_id:
        stmt = stmt.where(RunRecord.experiment_id == experiment_id)
    if limit:
        stmt = stmt.limit(limit)
    runs = session.scalars(stmt).all()
    created: list[dict[str, Any]] = []
    for run in runs:
        for annotator in annotators:
            existing = session.scalar(
                select(AnnotationRecord).where(
                    AnnotationRecord.run_id == run.id,
                    AnnotationRecord.finding_id.is_(None),
                    AnnotationRecord.annotator == annotator,
                )
            )
            if existing is not None:
                continue
            row = AnnotationRecord(
                run_id=run.id,
                annotation_scope="run",
                queue_status="assigned",
                annotator=annotator,
                label="unassigned",
                rationale="Assigned for review.",
            )
            session.add(row)
            session.flush()
            created.append(_record_dict(row))
    return created


def compute_annotation_agreement(session: Session, *, experiment_id: str | None = None) -> dict[str, Any]:
    """Compute basic label agreement and flag disagreements for adjudication."""
    stmt = select(AnnotationRecord).where(AnnotationRecord.queue_status == "submitted")
    if experiment_id:
        stmt = stmt.join(RunRecord, RunRecord.id == AnnotationRecord.run_id).where(
            RunRecord.experiment_id == experiment_id
        )
    rows = session.scalars(stmt).all()
    groups: dict[tuple[str, str | None], list[AnnotationRecord]] = {}
    for row in rows:
        groups.setdefault((row.run_id, row.finding_id), []).append(row)
    comparable = 0
    agreements = 0
    disagreements = 0
    for group in groups.values():
        if len(group) < 2:
            continue
        comparable += 1
        labels = {item.label for item in group}
        correctness = {item.correctness_verdict for item in group}
        security = {item.security_verdict for item in group}
        if len(labels) == 1 and len(correctness) <= 1 and len(security) <= 1:
            agreements += 1
            continue
        disagreements += 1
        for item in group:
            item.queue_status = "needs_adjudication"
    return {
        "comparable_items": comparable,
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_rate": agreements / comparable if comparable else None,
    }


def update_annotation_status(session: Session, annotation_id: str, status: str) -> dict[str, Any]:
    """Move an annotation through the queue/status workflow."""
    if status not in ANNOTATION_STATES:
        raise ValueError(f"unsupported annotation queue_status: {status}")
    row = session.get(AnnotationRecord, annotation_id)
    if row is None:
        raise KeyError(annotation_id)
    row.queue_status = status
    if status == "submitted" and row.submitted_at is None:
        row.submitted_at = datetime.now(UTC)
    session.flush()
    return _record_dict(row)


def list_adjudications(session: Session, *, run_id: str | None = None) -> list[dict[str, Any]]:
    """Return final adjudications, optionally scoped to one run."""
    stmt = select(AdjudicationRecord)
    if run_id:
        stmt = stmt.where(AdjudicationRecord.run_id == run_id)
    rows = session.scalars(stmt.order_by(AdjudicationRecord.created_at.desc())).all()
    return [_record_dict(row) for row in rows]


def create_adjudication(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a final adjudicated label and mark related annotations adjudicated."""
    row = AdjudicationRecord(
        run_id=str(payload["run_id"]),
        evaluation_id=payload.get("evaluation_id"),
        finding_id=payload.get("finding_id"),
        final_label=str(payload["final_label"]),
        final_correctness_verdict=payload.get("final_correctness_verdict"),
        final_security_verdict=payload.get("final_security_verdict"),
        final_severity=payload.get("final_severity"),
        adjudicator=str(payload["adjudicator"]),
        rationale=str(payload["rationale"]),
    )
    session.add(row)
    stmt = select(AnnotationRecord).where(AnnotationRecord.run_id == row.run_id)
    if row.finding_id:
        stmt = stmt.where(AnnotationRecord.finding_id == row.finding_id)
    else:
        stmt = stmt.where(AnnotationRecord.finding_id.is_(None))
    for annotation in session.scalars(stmt).all():
        annotation.queue_status = "adjudicated"
    session.flush()
    return _record_dict(row)


def list_experiments(session: Session) -> list[dict[str, Any]]:
    """Return known experiment designs."""
    rows = session.scalars(select(ExperimentRecord).order_by(ExperimentRecord.created_at.desc())).all()
    return [_record_dict(row) for row in rows]


def create_experiment(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Create or update an experiment design by name."""
    name = str(payload["name"])
    row = session.scalar(select(ExperimentRecord).where(ExperimentRecord.name == name))
    values = {
        "description": payload.get("description"),
        "design": dict(payload.get("design", payload)),
        "source_file": payload.get("source_file"),
        "source_file_hash": payload.get("source_file_hash"),
    }
    if row is None:
        row = ExperimentRecord(name=name, **values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    session.flush()
    return _record_dict(row)


def selected_text_matches(*, selected_text: str, selected_text_hash: str) -> bool:
    """Return whether selected evidence text still matches its stored hash."""
    return sha256_text(selected_text) == selected_text_hash


def _validated_selected_text_hash(
    session: Session,
    payload: dict[str, Any],
    selected_text: str,
) -> str | None:
    """Validate or derive the selected-text hash for an artifact span."""
    supplied = payload.get("selected_text_hash")
    artifact_id = payload.get("artifact_id")
    start_line = payload.get("start_line")
    end_line = payload.get("end_line")
    if artifact_id and start_line is not None and end_line is not None:
        span = _artifact_line_span(session, str(artifact_id), int(start_line), int(end_line))
        current_hash = sha256_text(span)
        if supplied and supplied != current_hash:
            raise ValueError("selected_text_hash does not match the current artifact span")
        if selected_text and sha256_text(selected_text) != current_hash:
            raise ValueError("selected_text does not match the current artifact span")
        return current_hash
    if supplied:
        if selected_text and supplied != sha256_text(selected_text):
            raise ValueError("selected_text_hash does not match selected_text")
        return str(supplied)
    return sha256_text(selected_text) if selected_text else None


def _artifact_line_span(session: Session, artifact_id: str, start_line: int, end_line: int) -> str:
    """Return the inclusive line span text for an artifact."""
    if start_line < 1 or end_line < start_line:
        raise ValueError("invalid artifact evidence line range")
    artifact = session.get(ArtifactRecord, artifact_id)
    if artifact is None:
        raise KeyError(f"artifact not found: {artifact_id}")
    text = Path(artifact.storage_path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    if start_line > len(lines):
        raise ValueError("artifact evidence start_line is outside the artifact content")
    return "".join(lines[start_line - 1 : min(end_line, len(lines))])


def list_prompts(
    session: Session,
    *,
    instance_id: str | None = None,
    skill_level: str | None = None,
    task_family: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return prompt variants with optional instance filters."""
    stmt = select(PromptVariantRecord, BenchmarkInstanceRecord).join(
        BenchmarkInstanceRecord,
        BenchmarkInstanceRecord.instance_id == PromptVariantRecord.instance_id,
    )
    if instance_id:
        stmt = stmt.where(PromptVariantRecord.instance_id == instance_id)
    if skill_level:
        stmt = stmt.where(PromptVariantRecord.skill_level == skill_level)
    if task_family:
        stmt = stmt.where(BenchmarkInstanceRecord.task_family == task_family)
    rows = session.execute(stmt.order_by(PromptVariantRecord.variant_name).limit(limit)).all()
    results: list[dict[str, Any]] = []
    for variant, instance in rows:
        item = _record_dict(variant)
        item["task_family"] = instance.task_family
        item["subject_area"] = instance.subject_area
        results.append(item)
    return results


def get_prompt(session: Session, prompt_id: str) -> dict[str, Any] | None:
    """Return one prompt variant by id."""
    row = session.get(PromptVariantRecord, prompt_id)
    if row is None:
        return None
    item = _record_dict(row)
    instance = session.get(BenchmarkInstanceRecord, row.instance_id)
    if instance:
        item["task_family"] = instance.task_family
        item["subject_area"] = instance.subject_area
    return item


def create_prompt(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a custom prompt variant."""
    instance_id = payload.get("instance_id")
    if not instance_id:
        raise ValueError("instance_id is required to create a prompt variant")
    instance = session.get(BenchmarkInstanceRecord, instance_id)
    if instance is None:
        raise KeyError(f"instance not found: {instance_id}")
    skill_level = str(payload.get("skill_level") or instance.skill_level)
    prompt_style = str(payload.get("prompt_style") or instance.prompt_style or "default")

    row = PromptVariantRecord(
        instance_id=instance_id,
        variant_name=str(payload["variant_name"]),
        skill_level=skill_level,
        prompt_style=prompt_style,
        prompt_text=str(payload["prompt_text"]),
        metadata_json=dict(payload.get("metadata_json", payload.get("metadata", {}))),
    )
    session.add(row)
    session.flush()
    return get_prompt(session, row.id) or _record_dict(row)


def update_prompt(session: Session, prompt_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Update prompt text and metadata for a variant."""
    row = session.get(PromptVariantRecord, prompt_id)
    if row is None:
        raise KeyError(prompt_id)
    if "prompt_text" in payload:
        row.prompt_text = str(payload["prompt_text"])
    if "metadata_json" in payload or "metadata" in payload:
        row.metadata_json = dict(payload.get("metadata_json", payload.get("metadata", row.metadata_json)))
    if "variant_name" in payload:
        row.variant_name = str(payload["variant_name"])
    session.flush()
    return get_prompt(session, prompt_id) or _record_dict(row)


def duplicate_prompt(session: Session, prompt_id: str, *, variant_name: str | None = None) -> dict[str, Any]:
    """Clone a prompt variant with a new name."""
    source = session.get(PromptVariantRecord, prompt_id)
    if source is None:
        raise KeyError(prompt_id)
    metadata = dict(source.metadata_json)
    metadata["duplicated_from"] = prompt_id
    new_name = variant_name or f"{source.variant_name}_copy"
    row = PromptVariantRecord(
        instance_id=source.instance_id,
        variant_name=new_name,
        skill_level=source.skill_level,
        prompt_style=source.prompt_style,
        prompt_text=source.prompt_text,
        metadata_json=metadata,
    )
    session.add(row)
    session.flush()
    return get_prompt(session, row.id) or _record_dict(row)


def list_prompt_templates(session: Session, *, limit: int = 200) -> list[dict[str, Any]]:
    """Return judge/generation prompt templates."""
    rows = session.scalars(
        select(PromptTemplateRecord).order_by(PromptTemplateRecord.name, PromptTemplateRecord.version).limit(limit)
    ).all()
    return [_record_dict(row) for row in rows]


def list_jobs(
    session: Session,
    *,
    limit: int = 100,
    status: str | None = None,
    kind: str | None = None,
    reconcile_stale: bool = True,
) -> list[dict[str, Any]]:
    """Return async jobs for the workbench queue."""
    from .jobs import _job_dict, reconcile_stale_jobs

    if reconcile_stale:
        reconcile_stale_jobs(session)
    stmt = select(JobRecord).order_by(JobRecord.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(JobRecord.status == status)
    if kind:
        stmt = stmt.where(JobRecord.kind == kind)
    rows = session.scalars(stmt).all()
    return [_job_dict(row) for row in rows]


def _record_dict(record: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for attr in sqlalchemy_inspect(record).mapper.column_attrs:
        column = attr.columns[0]
        value = getattr(record, attr.key)
        data[column.name] = value
        if attr.key != column.name:
            data[attr.key] = value
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data

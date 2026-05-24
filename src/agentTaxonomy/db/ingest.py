"""Ingest raw catalog and run artifacts into the research workbench database."""

from __future__ import annotations

import json
import mimetypes
import shutil
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    ArtifactRecord,
    ArtifactVersionRecord,
    BenchmarkInstanceRecord,
    EvaluationRecord,
    FindingRecord,
    PromptVariantRecord,
    RepoTargetRecord,
    RunRecord,
    SandboxProfileRecord,
    ScoreRecord,
    TaskRepoBindingRecord,
    TraceEventRecord,
)
from .session import init_database, project_root, session_scope

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", "target", "dist", "build"}
RUN_ARTIFACT_NAMES = {
    "agent_output.md",
    "prompt.md",
    "request.json",
    "raw_response.json",
    "trace.jsonl",
    "score.json",
    "audit.json",
    "supply_chain.json",
    "commands.log",
    "stdout.log",
    "stdout.txt",
    "stderr.log",
    "stderr.txt",
    "final.diff",
    "diff.patch",
    "git_status.txt",
    "untracked_files.txt",
    "changed_files.json",
    "scope_report.json",
    "tests.json",
    "oracle_results.json",
    "oracle.stdout.txt",
    "oracle.stderr.txt",
    "network.log",
    "network_events.jsonl",
    "sandbox_events.jsonl",
    "sandbox_profile.json",
    "fs_snapshot_before.json",
    "fs_snapshot_after.json",
    "repo_before.sha256",
    "repo_after.sha256",
}

REPO_ARTIFACT_TYPES = {
    "diff.patch": "repo_diff",
    "final.diff": "repo_diff",
    "changed_files.json": "repo_changed_files",
    "scope_report.json": "repo_scope",
    "tests.json": "repo_tests",
    "oracle_results.json": "repo_oracles",
    "sandbox_events.jsonl": "sandbox_events",
    "commands.log": "commands",
    "stdout.txt": "agent_stdout",
    "stderr.txt": "agent_stderr",
    "sandbox_profile.json": "sandbox_profile",
}


class IngestConflict(RuntimeError):
    """Raised when a source path was previously ingested with different content."""


@dataclass(frozen=True)
class IngestResult:
    """Outcome of an ingest operation.

    Attributes:
        record_id: Primary key of the run or catalog-like record that was touched.
        status: ``created``, ``updated``, or ``noop``.
        ingest_version: Numeric ingest version for repeated changed-source imports.
        source_hash: SHA-256 hash for the ingested source path.
    """

    record_id: str
    status: str
    ingest_version: int
    source_hash: str


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hash for a file."""
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    """Return the SHA-256 hash for a Unicode string."""
    return sha256(text.encode("utf-8")).hexdigest()


def hash_source_path(path: Path) -> str:
    """Hash a file or directory in a deterministic order for ingest idempotency."""
    path = path.resolve()
    if path.is_file():
        return sha256_file(path)
    digest = sha256()
    for item in _iter_source_files(path):
        relative = item.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(item).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def ingest_catalog(catalog_path: Path, *, database_url: str | None = None) -> IngestResult:
    """Index benchmark catalog instances into the workbench database."""
    init_database(database_url)
    catalog_path = catalog_path.resolve()
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    source_hash = sha256_file(catalog_path)
    instances = payload.get("instances", [])
    with session_scope(database_url) as session:
        for raw in instances:
            _upsert_instance(session, raw, catalog_path, source_hash)
            _upsert_default_repo_binding(session, raw, catalog_path, source_hash)
        return IngestResult(
            record_id=str(catalog_path),
            status="updated",
            ingest_version=1,
            source_hash=source_hash,
        )


def ingest_runs(
    runs_root: Path,
    *,
    database_url: str | None = None,
    new_ingest_version: bool = False,
) -> list[IngestResult]:
    """Ingest every directory below ``runs_root`` that contains a run trace or score."""
    results: list[IngestResult] = []
    for run_dir in sorted(_discover_run_dirs(runs_root)):
        results.append(
            ingest_run(
                run_dir,
                database_url=database_url,
                new_ingest_version=new_ingest_version,
            )
        )
    return results


def ingest_run(
    run_dir: Path,
    *,
    database_url: str | None = None,
    artifact_root: Path | None = None,
    new_ingest_version: bool = False,
) -> IngestResult:
    """Index one raw run directory with idempotent source-hash conflict rules."""
    init_database(database_url)
    run_dir = run_dir.resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"run directory not found: {run_dir}")
    source_hash = hash_source_path(run_dir)
    from agentTaxonomy.env import artifact_root as default_artifact_root

    artifact_root = artifact_root or default_artifact_root()
    with session_scope(database_url) as session:
        existing = _latest_run_for_dir(session, run_dir)
        if existing and existing.source_file_hash == source_hash:
            return IngestResult(existing.id, "noop", _numeric_ingest_version(existing), source_hash)
        if existing and not new_ingest_version:
            raise IngestConflict(
                f"{run_dir} was already ingested with hash {existing.source_file_hash}; "
                f"new hash is {source_hash}. Use --new-ingest-version to refresh the indexed run."
            )
        if existing:
            return _reingest_existing_run(
                session,
                existing,
                run_dir,
                source_hash,
                artifact_root,
            )

        version = 1
        run = _create_run_record(session, run_dir, source_hash, version)
        session.flush()
        _ingest_run_children(session, run, run_dir, source_hash, artifact_root, version)
        return IngestResult(run.id, "created", version, source_hash)


def ingest_evaluation(
    run_dir: Path,
    *,
    evidence_condition: str,
    database_url: str | None = None,
) -> IngestResult:
    """Create one additional evaluation view for the latest ingested run directory."""
    init_database(database_url)
    run_dir = run_dir.resolve()
    source_hash = hash_source_path(run_dir)
    with session_scope(database_url) as session:
        run = _latest_run_for_dir(session, run_dir)
        if run is None:
            raise FileNotFoundError(f"run directory has not been ingested: {run_dir}")
        evaluation = _ingest_evaluation_and_score(
            session,
            run,
            run_dir,
            source_hash,
            _numeric_ingest_version(run),
            evidence_condition=evidence_condition,
        )
        if evaluation is None:
            raise FileNotFoundError(f"score.json not found in run directory: {run_dir}")
        _ingest_findings(session, run, evaluation, run_dir, source_hash, _numeric_ingest_version(run))
        return IngestResult(evaluation.id, "created", _numeric_ingest_version(run), source_hash)


def rescore_run(
    run_id: str,
    *,
    evidence_condition: str,
    database_url: str | None = None,
) -> IngestResult:
    """Create a new score/evaluation view for an already indexed run."""
    init_database(database_url)
    with session_scope(database_url) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise KeyError(run_id)
        run_dir = Path(run.run_dir)
        named_score = run_dir / f"score_{evidence_condition}.json"
        score_file = named_score if named_score.exists() else run_dir / "score.json"
        evaluation = _ingest_evaluation_and_score(
            session,
            run,
            run_dir,
            run.source_file_hash or hash_source_path(run_dir),
            _numeric_ingest_version(run),
            score_file=score_file,
            evidence_condition=evidence_condition,
        )
        if evaluation is None:
            raise FileNotFoundError(f"no score file for {evidence_condition} in run directory: {run_dir}")
        return IngestResult(evaluation.id, "created", _numeric_ingest_version(run), run.source_file_hash or "")


def _upsert_instance(session: Session, raw: dict[str, Any], catalog_path: Path, source_hash: str) -> None:
    instance_id = str(raw["instance_id"])
    record = session.get(BenchmarkInstanceRecord, instance_id)
    task_id = instance_id.rsplit("__", 1)[0]
    metadata = {
        "raw": raw,
        "tags": raw.get("tags", []),
        "runtime_profiles": raw.get("runtime_profiles", []),
        "utility_oracles": raw.get("utility_oracles", {}),
        "hard_safety_oracles": raw.get("hard_safety_oracles", {}),
        "soft_review_rubric": raw.get("soft_review_rubric", {}),
        "expected_artifacts": raw.get("expected_artifacts", []),
        "allowed_output_files": raw.get("allowed_output_files", []),
        "protected_files": raw.get("protected_files", []),
        "hidden_oracle_command": raw.get("hidden_oracle_command"),
        "setup_command": raw.get("setup_command"),
        "teardown_command": raw.get("teardown_command"),
        "max_changed_files": raw.get("max_changed_files"),
        "allowed_dependency_files": raw.get("allowed_dependency_files", []),
        "forbidden_dependency_files": raw.get("forbidden_dependency_files", []),
        "domain_failure_modes": raw.get("domain_failure_modes", []),
    }
    values = {
        "task_id": task_id,
        "task_family": raw.get("task_family") or task_id,
        "task_mode": raw["task_mode"],
        "task_variant": raw.get("task_variant"),
        "prompt_style": raw.get("prompt_style"),
        "problem_class": raw["problem_class"],
        "subject_area": raw["subject_area"],
        "skill_level": raw["skill_level"],
        "permission_scope": raw["permission_scope"],
        "consequence_class": raw["consequence_class"],
        "expected_safe_outcome": raw["expected_safe_outcome"],
        "prompt_path": raw.get("agent_prompt_path"),
        "agent_prompt": raw["agent_prompt"],
        "expected_failure_modes": list(raw.get("expected_failure_modes") or raw.get("domain_failure_modes") or []),
        "expected_correctness_oracles": list(raw.get("expected_correctness_oracles") or []),
        "expected_security_oracles": list(raw.get("expected_security_oracles") or []),
        "metadata_json": metadata,
        "source_file": str(catalog_path),
        "source_file_hash": source_hash,
    }
    if record is None:
        session.add(BenchmarkInstanceRecord(instance_id=instance_id, **values))
        return
    for key, value in values.items():
        setattr(record, key, value)


def _upsert_default_repo_binding(session: Session, raw: dict[str, Any], catalog_path: Path, source_hash: str) -> None:
    """Create/update the default local-fixture repo target for catalog repo tasks."""

    if raw.get("task_mode") != "repo_task" or not raw.get("repo"):
        return
    instance_id = str(raw["instance_id"])
    repo_path = str(raw["repo"])
    task_family = str(raw.get("task_family") or raw.get("task_id") or instance_id.split("__")[0])
    target = session.scalar(
        select(RepoTargetRecord).where(
            RepoTargetRecord.source_type == "local_fixture",
            RepoTargetRecord.repo_path == repo_path,
        )
    )
    target_values = {
        "name": f"{task_family} fixture",
        "source_type": "local_fixture",
        "repo_path": repo_path,
        "git_url": None,
        "git_ref": raw.get("base_commit"),
        "task_family": task_family,
        "tags": list(raw.get("tags", [])),
        "metadata_json": {
            "source": "catalog_default",
            "base_commit": raw.get("base_commit"),
            "task_id": raw.get("task_id"),
        },
        "source_file": str(catalog_path),
        "source_file_hash": source_hash,
    }
    if target is None:
        target = RepoTargetRecord(**target_values)
        session.add(target)
        session.flush()
    else:
        for key, value in target_values.items():
            setattr(target, key, value)

    binding = session.scalar(
        select(TaskRepoBindingRecord).where(
            TaskRepoBindingRecord.instance_id == instance_id,
            TaskRepoBindingRecord.repo_target_id == target.id,
        )
    )
    binding_values = {
        "is_default": True,
        "allowed_output_files": list(raw.get("allowed_output_files", [])),
        "protected_files": list(raw.get("protected_files", [])),
        "utility_command": raw.get("utility_oracles", {}).get("command") if isinstance(raw.get("utility_oracles"), dict) else None,
        "hidden_oracle_command": raw.get("hidden_oracle_command"),
        "runtime_profiles": list(raw.get("runtime_profiles", [])),
        "metadata_json": {
            "source": "catalog_default",
            "repo": repo_path,
            "max_changed_files": raw.get("max_changed_files"),
            "allowed_dependency_files": raw.get("allowed_dependency_files", []),
            "forbidden_dependency_files": raw.get("forbidden_dependency_files", []),
        },
        "source_file": str(catalog_path),
        "source_file_hash": source_hash,
    }
    if binding is None:
        session.add(
            TaskRepoBindingRecord(
                instance_id=instance_id,
                repo_target_id=target.id,
                **binding_values,
            )
        )
        return
    for key, value in binding_values.items():
        setattr(binding, key, value)


def _resolve_task_mode(
    session: Session,
    *,
    instance_id: str | None,
    score: dict[str, Any],
    trace: list[dict[str, Any]],
    run_dir: Path,
) -> str | None:
    """Resolve task_mode from score, catalog instance, trace, or run artifacts."""
    mode = score.get("task_mode")
    if mode:
        return str(mode)
    if instance_id:
        instance = session.get(BenchmarkInstanceRecord, instance_id)
        if instance and instance.task_mode:
            return instance.task_mode
    for event in trace:
        payload = event.get("payload", {})
        if isinstance(payload, dict) and payload.get("task_mode"):
            return str(payload["task_mode"])
    if (run_dir / "sandbox_profile.json").exists() or (run_dir / "worktree").exists():
        return "repo_task"
    if (run_dir / "request.json").exists() and _load_json(run_dir / "request.json").get("model"):
        return "generative_task"
    return None


def _populate_run_record(
    session: Session,
    run: RunRecord,
    run_dir: Path,
    source_hash: str,
    ingest_version: int,
) -> None:
    """Fill run metadata from on-disk artifacts."""
    score = _load_json(run_dir / "score.json")
    request = _load_json(run_dir / "request.json")
    trace = _load_trace_lines(run_dir / "trace.jsonl")
    instance_id = _infer_instance_id(score, trace)
    run.instance_id = instance_id
    run.run_slug = run_dir.name
    run.run_dir = str(run_dir)
    run.task_mode = _resolve_task_mode(
        session,
        instance_id=instance_id,
        score=score,
        trace=trace,
        run_dir=run_dir,
    )
    run.agent_name = _infer_agent_name(request, run_dir)
    run.model_name = request.get("model") or _trace_model(trace)
    run.status = "completed" if score or (run_dir / "agent_output.md").exists() else "unknown"
    run.exit_code = _infer_exit_code(run_dir)
    run.sandbox_profile_name = _sandbox_profile_name(run_dir)
    run.sandbox_profile_hash = _sandbox_profile_hash(run_dir)
    prompt_id = request.get("prompt_id") or None
    run.prompt_variant_id = prompt_id if prompt_id and session.get(PromptVariantRecord, str(prompt_id)) else None
    agent_config = {
        "agent": request.get("agent"),
        "agent_cmd_template": request.get("agent_cmd_template"),
        "sandbox_profile": request.get("sandbox_profile"),
    }
    run.metadata_json = {
        "request": request,
        "repo_target_id": request.get("repo_target_id"),
        "repo_source_type": request.get("repo_source_type"),
        "repo_path": request.get("repo_source"),
        "git_url": request.get("repo_source") if request.get("repo_source_type") == "git" else None,
        "git_checkout_dir": request.get("repo_checkout_dir"),
        "runtime_profile": request.get("profile"),
        "agent_config": {key: value for key, value in agent_config.items() if value is not None},
        "relative_run_dir": _safe_relative(run_dir),
        "source_files": [path.relative_to(run_dir).as_posix() for path in _iter_source_files(run_dir)],
    }
    run.source_file = str(run_dir)
    run.source_file_hash = source_hash
    run.ingest_version = f"ingest.v{ingest_version}"


def _create_run_record(session: Session, run_dir: Path, source_hash: str, ingest_version: int) -> RunRecord:
    run = RunRecord()
    _populate_run_record(session, run, run_dir, source_hash, ingest_version)
    session.add(run)
    return run


def _clear_run_children(session: Session, run: RunRecord) -> None:
    """Remove prior indexed artifacts, trace, evaluations, and findings for a run refresh."""
    for collection in (run.evaluations, run.artifacts, run.trace_events, run.findings):
        for item in list(collection):
            session.delete(item)
    session.flush()


def _ingest_run_children(
    session: Session,
    run: RunRecord,
    run_dir: Path,
    source_hash: str,
    artifact_root: Path,
    ingest_version: int,
) -> None:
    """Index artifacts, trace, score, and findings for one run row."""
    _ingest_artifacts(session, run, run_dir, artifact_root, ingest_version)
    _ingest_trace(session, run, run_dir, source_hash, ingest_version)
    score_files = sorted(run_dir.glob("score_code_*.json"))
    if not score_files and (run_dir / "score.json").exists():
        score_files = [run_dir / "score.json"]
    if score_files:
        for score_file in score_files:
            if score_file.name == "score.json":
                condition = None
            else:
                condition = score_file.stem.removeprefix("score_")
            evaluation = _ingest_evaluation_and_score(
                session,
                run,
                run_dir,
                source_hash,
                ingest_version,
                score_file=score_file,
                evidence_condition=condition or None,
            )
            if evaluation is not None:
                _ingest_findings(session, run, evaluation, run_dir, source_hash, ingest_version)
    else:
        evaluation = _ingest_evaluation_and_score(session, run, run_dir, source_hash, ingest_version)
        if evaluation is not None:
            _ingest_findings(session, run, evaluation, run_dir, source_hash, ingest_version)
    _ingest_sandbox_profile(session, run, run_dir)


def _reingest_existing_run(
    session: Session,
    run: RunRecord,
    run_dir: Path,
    source_hash: str,
    artifact_root: Path,
) -> IngestResult:
    """Refresh an existing run row when the on-disk run directory changed."""
    version = _numeric_ingest_version(run) + 1
    _populate_run_record(session, run, run_dir, source_hash, version)
    _clear_run_children(session, run)
    _ingest_run_children(session, run, run_dir, source_hash, artifact_root, version)
    return IngestResult(run.id, "updated", version, source_hash)


def _ingest_evaluation_and_score(
    session: Session,
    run: RunRecord,
    run_dir: Path,
    source_hash: str,
    ingest_version: int,
    *,
    score_file: Path | None = None,
    evidence_condition: str | None = None,
) -> EvaluationRecord | None:
    score_path = score_file or (run_dir / "score.json")
    score = _load_json(score_path)
    if not score:
        return None
    request = _load_json(run_dir / "request.json")
    audit_exists = (run_dir / "audit.json").exists()
    supply_exists = (run_dir / "supply_chain.json").exists()
    trace_exists = (run_dir / "trace.jsonl").exists()
    condition = (
        evidence_condition
        or score.get("evidence_condition")
        or ("code_plus_trace" if trace_exists else "code_only")
    )
    include_trace = condition == "code_plus_trace" and trace_exists
    include_audit = condition == "code_plus_trace" and audit_exists
    include_supply_chain = condition == "code_plus_trace" and supply_exists
    evaluation = EvaluationRecord(
        run_id=run.id,
        evaluation_kind="automated_score",
        evidence_condition=condition,
        verification_tier=score.get("verification_tier"),
        status="completed",
        scorer_version="agentTaxonomy.scoring.v1",
        audit_version=_report_version(run_dir / "audit.json", "static_audit.v1") if audit_exists else None,
        supply_chain_version=_report_version(run_dir / "supply_chain.json", "supply_chain.v1") if supply_exists else None,
        judge_model=_judge_model(request, score),
        judge_prompt_version="soft_judge_prompt.v1",
        evaluation_inputs={
            "agent_output": _path_input(run_dir, "agent_output.md"),
            "trace": _path_input(run_dir, "trace.jsonl") if include_trace else None,
            "audit": _path_input(run_dir, "audit.json") if include_audit else None,
            "supply_chain": _path_input(run_dir, "supply_chain.json") if include_supply_chain else None,
            "included_sources": {
                "code": (run_dir / "agent_output.md").exists() or (run_dir / "extracted").exists(),
                "trace": include_trace,
                "audit": include_audit,
                "supply_chain": include_supply_chain,
            },
        },
        final_outcome_class=_derive_outcome_class(score),
        professor_hierarchy_level=_derive_hierarchy_level(score),
        dominant_failure_category=_dominant_failure(score),
        security_relevant_even_if_correct=bool(score.get("utility_score", {}).get("solved", False) and score.get("security_adjusted_success", 0.0) == 0.0),
        model_introduced_vulnerability=None,
        source_file=str(score_path),
        source_file_hash=sha256_file(score_path),
        ingest_version=f"ingest.v{ingest_version}",
    )
    session.add(evaluation)
    session.flush()
    if not run.task_mode:
        resolved = _resolve_task_mode(
            session,
            instance_id=run.instance_id,
            score=score,
            trace=_load_trace_lines(run_dir / "trace.jsonl"),
            run_dir=run_dir,
        )
        if resolved:
            run.task_mode = resolved
    session.add(
        ScoreRecord(
            evaluation_id=evaluation.id,
            utility_score=_nested_score(score, "utility_score"),
            hard_safety_score=_nested_score(score, "hard_safety_score"),
            soft_safety_score=_nested_score(score, "soft_safety_score"),
            security_adjusted_success=score.get("security_adjusted_success"),
            provisional_security_success=score.get("provisional_security_success"),
            positive_security_verified=score.get("positive_security_verified"),
            review_status=score.get("review_status"),
            verification_tier=score.get("verification_tier"),
            scorer_version=evaluation.scorer_version,
            audit_version=evaluation.audit_version,
            supply_chain_version=evaluation.supply_chain_version,
            judge_model=evaluation.judge_model,
            judge_prompt_version=evaluation.judge_prompt_version,
            score_json=score,
            source_file=str(run_dir / "score.json"),
            source_file_hash=sha256_file(run_dir / "score.json"),
            ingest_version=f"ingest.v{ingest_version}",
        )
    )
    return evaluation


def _ingest_artifacts(
    session: Session,
    run: RunRecord,
    run_dir: Path,
    artifact_root: Path,
    ingest_version: int,
) -> None:
    artifact_root.mkdir(parents=True, exist_ok=True)
    for path in _iter_artifact_files(run_dir):
        relative = path.relative_to(run_dir).as_posix()
        content_hash = sha256_file(path)
        storage = _copy_content_addressed(path, artifact_root, content_hash)
        upsert_artifact_revision(
            session,
            run_id=run.id,
            logical_path=relative,
            artifact_type=_artifact_type(path, relative),
            content_hash=content_hash,
            storage_path=str(storage),
            size_bytes=path.stat().st_size,
            mime_type=mimetypes.guess_type(path.name)[0],
            source_file=str(path),
            source_file_hash=content_hash,
            ingest_version=f"ingest.v{ingest_version}",
        )


def upsert_artifact_revision(
    session: Session,
    *,
    run_id: str,
    logical_path: str,
    artifact_type: str,
    content_hash: str,
    storage_path: str,
    size_bytes: int | None,
    mime_type: str | None,
    source_file: str,
    source_file_hash: str,
    ingest_version: str,
) -> ArtifactRecord:
    """Create or revise an artifact for a stable logical path in one run."""
    artifact = session.scalar(
        select(ArtifactRecord).where(
            ArtifactRecord.run_id == run_id,
            ArtifactRecord.logical_path == logical_path,
        )
    )
    if artifact is None:
        artifact = ArtifactRecord(
            run_id=run_id,
            logical_path=logical_path,
            artifact_type=artifact_type,
            content_hash=content_hash,
            storage_path=storage_path,
            size_bytes=size_bytes,
            mime_type=mime_type,
            source_file=source_file,
            source_file_hash=source_file_hash,
            ingest_version=ingest_version,
        )
        session.add(artifact)
        session.flush()
        session.add(
            ArtifactVersionRecord(
                artifact_id=artifact.id,
                revision=1,
                content_hash=content_hash,
                storage_path=storage_path,
                size_bytes=size_bytes,
                source_file=source_file,
                source_file_hash=source_file_hash,
                ingest_version=ingest_version,
            )
        )
        return artifact
    if artifact.content_hash == content_hash:
        return artifact
    latest = session.scalar(
        select(func.max(ArtifactVersionRecord.revision)).where(ArtifactVersionRecord.artifact_id == artifact.id)
    ) or 0
    artifact.content_hash = content_hash
    artifact.storage_path = storage_path
    artifact.size_bytes = size_bytes
    artifact.mime_type = mime_type
    artifact.source_file = source_file
    artifact.source_file_hash = source_file_hash
    artifact.ingest_version = ingest_version
    session.add(
        ArtifactVersionRecord(
            artifact_id=artifact.id,
            revision=int(latest) + 1,
            content_hash=content_hash,
            storage_path=storage_path,
            size_bytes=size_bytes,
            source_file=source_file,
            source_file_hash=source_file_hash,
            ingest_version=ingest_version,
        )
    )
    return artifact


def _ingest_trace(session: Session, run: RunRecord, run_dir: Path, source_hash: str, ingest_version: int) -> None:
    trace_path = run_dir / "trace.jsonl"
    if not trace_path.exists():
        return
    for seq, event in enumerate(_load_trace_lines(trace_path), start=1):
        session.add(
            TraceEventRecord(
                run_id=run.id,
                seq=seq,
                event_id=event.get("event_id"),
                event_type=str(event.get("event_type", "unknown")),
                timestamp=event.get("timestamp"),
                actor=event.get("actor"),
                summary=_trace_summary(event),
                payload=event.get("payload", {}),
                source_file=str(trace_path),
                source_file_hash=source_hash,
                ingest_version=f"ingest.v{ingest_version}",
            )
        )


def _ingest_findings(
    session: Session,
    run: RunRecord,
    evaluation: EvaluationRecord,
    run_dir: Path,
    source_hash: str,
    ingest_version: int,
) -> None:
    audit = _load_json(run_dir / "audit.json")
    for item in audit.get("findings", []):
        if not isinstance(item, dict):
            continue
        session.add(
            FindingRecord(
                run_id=run.id,
                evaluation_id=evaluation.id,
                source="audit",
                category=str(item.get("gate") or item.get("id") or "audit"),
                subcategory=str(item.get("id")) if item.get("id") else None,
                severity=str(item.get("severity", "info")),
                confidence="medium",
                verdict="fail" if item.get("blocking") else "warning",
                file_path=item.get("path"),
                start_line=item.get("line"),
                end_line=item.get("line"),
                evidence_json=item,
                message=str(item.get("message") or item.get("evidence") or "Audit finding"),
                remediation=None,
                source_file=str(run_dir / "audit.json"),
                source_file_hash=sha256_file(run_dir / "audit.json") if (run_dir / "audit.json").exists() else source_hash,
                ingest_version=f"ingest.v{ingest_version}",
            )
        )
    supply = _load_json(run_dir / "supply_chain.json")
    for item in supply.get("findings", []):
        if not isinstance(item, dict):
            continue
        session.add(
            FindingRecord(
                run_id=run.id,
                evaluation_id=evaluation.id,
                source="supply_chain",
                category=str(item.get("gate") or item.get("kind") or "supply_chain"),
                severity=str(item.get("severity", "info")),
                confidence="medium",
                verdict="fail" if item.get("blocking") else "warning",
                evidence_json=item,
                message=str(item.get("message") or item.get("evidence") or "Supply-chain finding"),
                source_file=str(run_dir / "supply_chain.json"),
                source_file_hash=sha256_file(run_dir / "supply_chain.json") if (run_dir / "supply_chain.json").exists() else source_hash,
                ingest_version=f"ingest.v{ingest_version}",
            )
        )
    score = _load_json(run_dir / "score.json")
    for item in score.get("soft_safety_score", {}).get("items", []):
        if not isinstance(item, dict) or item.get("passed", False):
            continue
        session.add(
            FindingRecord(
                run_id=run.id,
                evaluation_id=evaluation.id,
                source="judge",
                category=str(item.get("rubric_id", "soft_review")),
                severity=str(item.get("severity", "medium")),
                confidence=_confidence_label(item.get("confidence")),
                verdict="fail",
                evidence_json=item,
                message=str(item.get("finding") or item.get("rationale") or "Soft-review failure"),
                remediation=item.get("action"),
                source_file=str(run_dir / "score.json"),
                source_file_hash=sha256_file(run_dir / "score.json") if (run_dir / "score.json").exists() else source_hash,
                ingest_version=f"ingest.v{ingest_version}",
            )
        )
    for gate in score.get("security_gate_verdicts", []):
        if not isinstance(gate, dict) or str(gate.get("verdict", "")).lower() != "fail":
            continue
        session.add(
            FindingRecord(
                run_id=run.id,
                evaluation_id=evaluation.id,
                source="score_gate",
                category=str(gate.get("name") or gate.get("gate_id") or "gate"),
                severity=str(gate.get("severity", "high")),
                confidence="medium",
                verdict="fail",
                evidence_json=gate,
                message=str(gate.get("finding") or gate.get("evidence") or "Security gate failed"),
                remediation=None,
                source_file=str(run_dir / "score.json"),
                source_file_hash=sha256_file(run_dir / "score.json") if (run_dir / "score.json").exists() else source_hash,
                ingest_version=f"ingest.v{ingest_version}",
            )
        )


def _ingest_sandbox_profile(session: Session, run: RunRecord, run_dir: Path) -> None:
    metadata_path = run_dir / "sandbox_profile.json"
    if metadata_path.exists():
        policy = _load_json(metadata_path)
        name = str(policy.get("name") or run.sandbox_profile_name or "unknown")
        profile_hash = str(policy.get("profile_hash") or sha256_text(json.dumps(policy, sort_keys=True)))
    elif run.sandbox_profile_name and run.sandbox_profile_hash:
        name = run.sandbox_profile_name
        profile_hash = run.sandbox_profile_hash
        policy = {"name": name, "profile_hash": profile_hash}
    else:
        return
    existing = session.scalar(select(SandboxProfileRecord).where(SandboxProfileRecord.profile_hash == profile_hash))
    if existing is not None:
        return
    session.add(
        SandboxProfileRecord(
            name=name,
            profile_hash=profile_hash,
            policy_json=policy,
            source_file=str(metadata_path) if metadata_path.exists() else run.source_file,
            source_file_hash=sha256_file(metadata_path) if metadata_path.exists() else run.source_file_hash,
        )
    )


def _discover_run_dirs(root: Path) -> Iterable[Path]:
    root = root.resolve()
    if (root / "trace.jsonl").exists() or (root / "score.json").exists():
        yield root
        return
    for path in root.rglob("*"):
        if path.is_dir() and ((path / "trace.jsonl").exists() or (path / "score.json").exists()):
            yield path


def _iter_source_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if SKIP_DIRS.intersection(path.relative_to(root).parts):
            continue
        yield path


def _iter_artifact_files(root: Path) -> Iterable[Path]:
    for path in _iter_source_files(root):
        relative = path.relative_to(root)
        if path.name in RUN_ARTIFACT_NAMES or "extracted" in relative.parts:
            yield path


def _copy_content_addressed(path: Path, artifact_root: Path, content_hash: str) -> Path:
    target = artifact_root / content_hash[:2] / content_hash
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)
    return target


def _latest_run_for_dir(session: Session, run_dir: Path) -> RunRecord | None:
    return session.scalar(
        select(RunRecord)
        .where(RunRecord.run_dir == str(run_dir))
        .order_by(RunRecord.ingested_at.desc())
        .limit(1)
    )


def _next_run_ingest_version(session: Session, run_dir: Path) -> int:
    existing = session.scalars(select(RunRecord).where(RunRecord.run_dir == str(run_dir))).all()
    if not existing:
        return 1
    return max(_numeric_ingest_version(item) for item in existing) + 1


def _numeric_ingest_version(record: RunRecord) -> int:
    try:
        return int(str(record.ingest_version).rsplit(".", 1)[-1].removeprefix("v"))
    except ValueError:
        return 1


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_trace_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _infer_instance_id(score: dict[str, Any], trace: list[dict[str, Any]]) -> str | None:
    if score.get("instance_id"):
        return str(score["instance_id"])
    for event in trace:
        payload = event.get("payload", {})
        if isinstance(payload, dict) and payload.get("instance_id"):
            return str(payload["instance_id"])
    return None


def _infer_agent_name(request: dict[str, Any], run_dir: Path) -> str:
    if request.get("agent"):
        return str(request["agent"])
    if request.get("model"):
        return "openrouter"
    if (run_dir / "commands.log").exists() or (run_dir / "stdout.log").exists():
        return "command"
    return "unknown"


def _trace_model(trace: list[dict[str, Any]]) -> str | None:
    for event in trace:
        payload = event.get("payload", {})
        if isinstance(payload, dict) and payload.get("model"):
            return str(payload["model"])
    return None


def _infer_exit_code(run_dir: Path) -> int | None:
    for path in [run_dir / "commands.log", run_dir / "tests.json"]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "returncode=" in text:
            raw = text.split("returncode=", 1)[1].splitlines()[0].strip()
            try:
                return int(raw)
            except ValueError:
                return None
    return None


def _sandbox_profile_name(run_dir: Path) -> str | None:
    path = run_dir / "sandbox_profile.json"
    if path.exists():
        return str(_load_json(path).get("name") or "unknown")
    return None


def _sandbox_profile_hash(run_dir: Path) -> str | None:
    path = run_dir / "sandbox_profile.json"
    if path.exists():
        data = _load_json(path)
        return str(data.get("profile_hash") or sha256_text(json.dumps(data, sort_keys=True)))
    return None


def _path_input(run_dir: Path, name: str) -> dict[str, Any]:
    path = run_dir / name
    return {"path": str(path), "hash": sha256_file(path), "bytes": path.stat().st_size}


def _report_version(path: Path, default: str) -> str:
    payload = _load_json(path)
    return str(payload.get("audit_version") or payload.get("supply_chain_version") or payload.get("version") or default)


def _judge_model(request: dict[str, Any], score: dict[str, Any]) -> str | None:
    return score.get("judge_model") or request.get("judge_model") or request.get("model")


def _nested_score(score: dict[str, Any], key: str) -> float | None:
    item = score.get(key)
    if isinstance(item, dict) and item.get("score") is not None:
        return float(item["score"])
    return None


def _derive_outcome_class(score: dict[str, Any]) -> str:
    if score.get("hard_safety_score", {}).get("catastrophic"):
        return "unsafe_action_or_catastrophic"
    if not score.get("utility_score", {}).get("solved", False):
        return "nonfunctional"
    if score.get("security_adjusted_success") == 1.0:
        return "correct_and_secure"
    if score.get("soft_safety_score", {}).get("binary_pass", False):
        return "secure_but_incomplete"
    return "correct_but_insecure"


def _derive_hierarchy_level(score: dict[str, Any]) -> str | None:
    outcome = _derive_outcome_class(score)
    if outcome == "nonfunctional":
        return "correctness"
    if outcome == "correct_but_insecure":
        return "latent_vulnerability"
    if "supply_chain_risk" in score.get("blocking_gates", []):
        return "supply_chain"
    if outcome == "unsafe_action_or_catastrophic":
        return "other_vulnerability"
    return None


def _dominant_failure(score: dict[str, Any]) -> str | None:
    blocking = score.get("blocking_gates") or []
    if blocking:
        return str(blocking[0])
    for item in score.get("soft_safety_score", {}).get("items", []):
        if isinstance(item, dict) and not item.get("passed", False):
            modes = item.get("failure_modes") or []
            return str(modes[0] if modes else item.get("rubric_id", "soft_review"))
    return None


def _confidence_label(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "medium"
    if numeric >= 0.8:
        return "high"
    if numeric >= 0.5:
        return "medium"
    return "low"


def _artifact_type(path: Path, relative: str) -> str:
    if path.name in REPO_ARTIFACT_TYPES:
        return REPO_ARTIFACT_TYPES[path.name]
    if path.name == "trace.jsonl":
        return "trace"
    if path.name == "score.json":
        return "score"
    if path.name == "audit.json":
        return "audit"
    if path.name == "supply_chain.json":
        return "supply_chain"
    if path.name in {"final.diff", "diff.patch"}:
        return "diff"
    if "extracted" in Path(relative).parts:
        return "extracted_artifact"
    return "run_artifact"


def _trace_summary(event: dict[str, Any]) -> str | None:
    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        return None
    for key in ["message", "command", "decision", "summary"]:
        if payload.get(key):
            return str(payload[key])[:500]
    return None


def _safe_relative(path: Path) -> str:
    try:
        return path.relative_to(project_root()).as_posix()
    except ValueError:
        return str(path)

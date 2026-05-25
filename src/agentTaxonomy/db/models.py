"""SQLAlchemy models for the local research workbench.

The database deliberately indexes raw JSON and trace artifacts instead of
replacing them. Each source-backed table carries schema and ingest provenance so
older benchmark outputs can be compared safely after schemas, scoring logic, or
judge prompts evolve.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

CURRENT_DB_SCHEMA_VERSION = "workbench.v1"
CURRENT_INGEST_VERSION = "ingest.v1"


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for DB defaults."""
    return datetime.now(UTC)


def new_uuid() -> str:
    """Return a UUID string suitable for primary keys."""
    return str(uuid4())


class Base(DeclarativeBase):
    """Declarative base for all workbench tables."""


class ProvenanceMixin:
    """Common provenance fields for source-backed research records."""

    schema_version: Mapped[str] = mapped_column(String(64), default=CURRENT_DB_SCHEMA_VERSION, nullable=False)
    source_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ingest_version: Mapped[str] = mapped_column(String(64), default=CURRENT_INGEST_VERSION, nullable=False)


class BenchmarkInstanceRecord(ProvenanceMixin, Base):
    """Catalog instance metadata indexed from ``benchmark/generated/catalog.json``."""

    __tablename__ = "benchmark_instances"

    instance_id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_id: Mapped[str] = mapped_column(Text, nullable=False)
    task_family: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    task_variant: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_style: Mapped[str | None] = mapped_column(String(64), nullable=True)
    problem_class: Mapped[str] = mapped_column(Text, nullable=False)
    subject_area: Mapped[str] = mapped_column(Text, nullable=False)
    skill_level: Mapped[str] = mapped_column(String(64), nullable=False)
    permission_scope: Mapped[str] = mapped_column(String(128), nullable=False)
    consequence_class: Mapped[str] = mapped_column(String(128), nullable=False)
    expected_safe_outcome: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_failure_modes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expected_correctness_oracles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expected_security_oracles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    runs: Mapped[list["RunRecord"]] = relationship(back_populates="instance")


class PromptVariantRecord(ProvenanceMixin, Base):
    """Prompt variant metadata for prompt-ladder and paired-task experiments."""

    __tablename__ = "prompt_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("benchmark_instances.instance_id"), nullable=False)
    variant_name: Mapped[str] = mapped_column(Text, nullable=False)
    skill_level: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_style: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


class ExperimentRecord(ProvenanceMixin, Base):
    """Experiment design metadata used to group runs and evaluations."""

    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    design: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    runs: Mapped[list["RunRecord"]] = relationship(back_populates="experiment")


class SandboxProfileRecord(ProvenanceMixin, Base):
    """Reproducible sandbox policy attached to repo-task agent executions."""

    __tablename__ = "sandbox_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class RepoTargetRecord(ProvenanceMixin, Base):
    """Repository target that a repo-task instance can run against."""

    __tablename__ = "repo_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    repo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    git_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    git_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_family: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    bindings: Mapped[list["TaskRepoBindingRecord"]] = relationship(
        back_populates="repo_target",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_repo_targets_task_family", "task_family"),
        Index("ix_repo_targets_source_type", "source_type"),
    )


class TaskRepoBindingRecord(ProvenanceMixin, Base):
    """Binding between a task instance and a repository target."""

    __tablename__ = "task_repo_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("benchmark_instances.instance_id"), nullable=False)
    repo_target_id: Mapped[str] = mapped_column(ForeignKey("repo_targets.id", ondelete="CASCADE"), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_output_files: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    protected_files: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    utility_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    hidden_oracle_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_profiles: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    repo_target: Mapped[RepoTargetRecord] = relationship(back_populates="bindings")

    __table_args__ = (
        UniqueConstraint("instance_id", "repo_target_id", name="uq_task_repo_binding_instance_target"),
        Index("ix_task_repo_bindings_instance", "instance_id"),
        Index("ix_task_repo_bindings_target", "repo_target_id"),
    )


class RunRecord(ProvenanceMixin, Base):
    """One physical agent execution over one benchmark instance."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    experiment_id: Mapped[str | None] = mapped_column(ForeignKey("experiments.id"), nullable=True)
    instance_id: Mapped[str | None] = mapped_column(ForeignKey("benchmark_instances.instance_id"), nullable=True)
    prompt_variant_id: Mapped[str | None] = mapped_column(ForeignKey("prompt_variants.id"), nullable=True)
    run_slug: Mapped[str] = mapped_column(Text, nullable=False)
    run_dir: Mapped[str] = mapped_column(Text, nullable=False)
    task_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sandbox_profile_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sandbox_profile_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    experiment: Mapped[ExperimentRecord | None] = relationship(back_populates="runs")
    instance: Mapped[BenchmarkInstanceRecord | None] = relationship(back_populates="runs")
    evaluations: Mapped[list["EvaluationRecord"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    artifacts: Mapped[list["ArtifactRecord"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    trace_events: Mapped[list["TraceEventRecord"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    findings: Mapped[list["FindingRecord"]] = relationship(back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_runs_run_dir", "run_dir"),
        Index("ix_runs_source_hash", "source_file_hash"),
    )


class EvaluationRecord(ProvenanceMixin, Base):
    """One scoring or review view over a run."""

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    evaluation_kind: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_condition: Mapped[str] = mapped_column(String(128), nullable=False)
    verification_tier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="completed", nullable=False)
    scorer_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    audit_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    supply_chain_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    judge_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evaluation_inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    final_outcome_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    professor_hierarchy_level: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dominant_failure_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    security_relevant_even_if_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    model_introduced_vulnerability: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[RunRecord] = relationship(back_populates="evaluations")
    score: Mapped["ScoreRecord | None"] = relationship(back_populates="evaluation", cascade="all, delete-orphan")
    findings: Mapped[list["FindingRecord"]] = relationship(back_populates="evaluation")

    __table_args__ = (
        Index("ix_evaluations_run_id", "run_id"),
        Index("ix_evaluations_condition", "evidence_condition"),
    )


class ScoreRecord(ProvenanceMixin, Base):
    """Normalized score headline fields plus the complete score JSON payload."""

    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.id", ondelete="CASCADE"), unique=True, nullable=False)
    utility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hard_safety_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    soft_safety_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    security_adjusted_success: Mapped[float | None] = mapped_column(Float, nullable=True)
    provisional_security_success: Mapped[float | None] = mapped_column(Float, nullable=True)
    positive_security_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    review_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verification_tier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scorer_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    audit_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    supply_chain_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    judge_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    score_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    evaluation: Mapped[EvaluationRecord] = relationship(back_populates="score")


class ArtifactRecord(ProvenanceMixin, Base):
    """Latest indexed revision for one logical artifact path in a run."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(128), nullable=False)
    logical_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_from: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    run: Mapped[RunRecord] = relationship(back_populates="artifacts")
    versions: Mapped[list["ArtifactVersionRecord"]] = relationship(back_populates="artifact", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("run_id", "logical_path", name="uq_artifact_run_logical_path"),
        Index("ix_artifacts_hash", "content_hash"),
    )


class ArtifactVersionRecord(ProvenanceMixin, Base):
    """Historical content revision for one logical artifact path."""

    __tablename__ = "artifact_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    artifact: Mapped[ArtifactRecord] = relationship(back_populates="versions")

    __table_args__ = (UniqueConstraint("artifact_id", "revision", name="uq_artifact_revision"),)


class TraceEventRecord(ProvenanceMixin, Base):
    """Trace event indexed from ``trace.jsonl`` for timeline and evidence queries."""

    __tablename__ = "trace_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    run: Mapped[RunRecord] = relationship(back_populates="trace_events")

    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_trace_event_run_seq"),
        Index("ix_trace_events_type", "event_type"),
    )


class FindingRecord(ProvenanceMixin, Base):
    """Observed issue from audit, judge, supply-chain, test, or human review."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    evaluation_id: Mapped[str | None] = mapped_column(ForeignKey("evaluations.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cwe_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[str] = mapped_column(String(64), nullable=False)
    verdict: Mapped[str] = mapped_column(String(64), nullable=False)
    introduced_by_model: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    selected_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    run: Mapped[RunRecord] = relationship(back_populates="findings")
    evaluation: Mapped[EvaluationRecord | None] = relationship(back_populates="findings")


class AnnotationRecord(ProvenanceMixin, Base):
    """Human label or verdict over either an entire run or a specific finding."""

    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    evaluation_id: Mapped[str | None] = mapped_column(ForeignKey("evaluations.id", ondelete="SET NULL"), nullable=True)
    finding_id: Mapped[str | None] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=True)
    annotation_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    queue_status: Mapped[str] = mapped_column(String(64), default="submitted", nullable=False)
    annotator: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    correctness_verdict: Mapped[str | None] = mapped_column(String(128), nullable=True)
    security_verdict: Mapped[str | None] = mapped_column(String(128), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    selected_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_annotations_run_status", "run_id", "queue_status"),
        Index("ix_annotations_finding_id", "finding_id"),
    )


class JobRecord(Base):
    """Durable async work item for generate, repo_run, judge, bootstrap, ingest, and rescore."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    phase: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_jobs_status", "status"), Index("ix_jobs_kind", "kind"))


class PromptTemplateRecord(ProvenanceMixin, Base):
    """System/developer/judge/generation prompt templates (not task prompts)."""

    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("name", "version", name="uq_prompt_template_name_version"),)


class AdjudicationRecord(ProvenanceMixin, Base):
    """Final adjudicated label for a disputed run or finding."""

    __tablename__ = "adjudications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    evaluation_id: Mapped[str | None] = mapped_column(ForeignKey("evaluations.id", ondelete="SET NULL"), nullable=True)
    finding_id: Mapped[str | None] = mapped_column(ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    final_label: Mapped[str] = mapped_column(String(128), nullable=False)
    final_correctness_verdict: Mapped[str | None] = mapped_column(String(128), nullable=True)
    final_security_verdict: Mapped[str | None] = mapped_column(String(128), nullable=True)
    final_severity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    adjudicator: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

"""DB-backed job queue for async workbench operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import JobRecord, new_uuid
from .session import session_scope

JOB_KINDS = {"generate", "repo_run", "judge", "bootstrap", "ingest", "rescore"}
JOB_STATUSES = {"queued", "running", "succeeded", "failed"}

# Max wall time before a queued/running job is marked failed (API reload can orphan workers).
STALE_JOB_MAX_AGE_SECONDS: dict[str, int] = {
    "generate": 300,
    "repo_run": 300,
    "judge": 900,
    "ingest": 180,
    "bootstrap": 900,
    "rescore": 180,
}
DEFAULT_STALE_JOB_MAX_AGE_SECONDS = 300

STALE_JOB_ERROR = (
    "Job exceeded the workbench time limit or the API restarted while it was running. "
    "OpenRouter usage may not appear until a request completes; re-run the task if needed."
)


def create_job(
    session: Session,
    *,
    kind: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert a queued job row and return its serialized form."""
    if kind not in JOB_KINDS:
        raise ValueError(f"unsupported job kind: {kind}")
    row = JobRecord(
        id=new_uuid(),
        kind=kind,
        status="queued",
        metadata_json=dict(metadata or {}),
    )
    session.add(row)
    session.flush()
    return _job_dict(row)


def set_job_phase(
    job_id: str,
    phase: str,
    *,
    database_url: str | None = None,
) -> None:
    """Update only the phase field (for long-running steps like OpenRouter)."""
    with session_scope(database_url) as session:
        update_job(session, job_id, phase=phase)


def reconcile_stale_jobs(
    session: Session,
    *,
    now: datetime | None = None,
) -> list[str]:
    """Mark queued/running jobs older than their per-kind limit as failed."""
    now = now or datetime.now(UTC)
    reconciled: list[str] = []
    rows = session.scalars(
        select(JobRecord).where(JobRecord.status.in_(("queued", "running")))
    ).all()
    for row in rows:
        started = row.started_at or row.created_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        age_seconds = (now - started).total_seconds()
        limit = STALE_JOB_MAX_AGE_SECONDS.get(row.kind, DEFAULT_STALE_JOB_MAX_AGE_SECONDS)
        if age_seconds <= limit:
            continue
        update_job(
            session,
            row.id,
            status="failed",
            error=f"{STALE_JOB_ERROR} (age={int(age_seconds)}s, limit={limit}s, phase={row.phase!r})",
        )
        reconciled.append(row.id)
    return reconciled


def get_job(session: Session, job_id: str) -> dict[str, Any] | None:
    """Return one job row by id."""
    row = session.get(JobRecord, job_id)
    return _job_dict(row) if row else None


def update_job(
    session: Session,
    job_id: str,
    *,
    status: str | None = None,
    phase: str | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update job status, phase, error, and/or metadata."""
    row = session.get(JobRecord, job_id)
    if row is None:
        raise KeyError(job_id)
    if status is not None:
        if status not in JOB_STATUSES:
            raise ValueError(f"unsupported job status: {status}")
        row.status = status
        if status == "running" and row.started_at is None:
            row.started_at = datetime.now(UTC)
        if status in {"succeeded", "failed"}:
            row.completed_at = datetime.now(UTC)
    if phase is not None:
        row.phase = phase
    if error is not None:
        row.error = error
    if metadata is not None:
        merged = dict(row.metadata_json)
        merged.update(metadata)
        row.metadata_json = merged
    session.flush()
    return _job_dict(row)


def run_job_in_background(
    job_id: str,
    worker: Callable[[str], None],
    *,
    database_url: str | None = None,
) -> None:
    """Execute a job worker in a fresh DB session (for FastAPI BackgroundTasks)."""
    try:
        with session_scope(database_url) as session:
            update_job(session, job_id, status="running")
        worker(job_id)
        with session_scope(database_url) as session:
            update_job(session, job_id, status="succeeded")
    except Exception as exc:
        with session_scope(database_url) as session:
            update_job(session, job_id, status="failed", error=str(exc))


def _job_dict(row: JobRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "status": row.status,
        "phase": row.phase,
        "error": row.error,
        "created_at": row.created_at.isoformat(),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "metadata_json": row.metadata_json,
        "result": row.metadata_json.get("result"),
    }

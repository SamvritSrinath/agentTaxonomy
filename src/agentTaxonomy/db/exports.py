"""Tabular exports for analysis notebooks and paper figures."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Session

from .models import (
    AdjudicationRecord,
    AnnotationRecord,
    BenchmarkInstanceRecord,
    EvaluationRecord,
    FindingRecord,
    RunRecord,
    ScoreRecord,
)
from .session import init_database, session_scope


def export_runs(output: Path, *, database_url: str | None = None) -> Path:
    """Export run rows to CSV or Parquet, based on the output extension."""
    init_database(database_url)
    with session_scope(database_url) as session:
        rows = [_row_dict(row) for row in session.scalars(select(RunRecord)).all()]
    _write_rows(output, rows)
    return output


def export_findings(output: Path, *, database_url: str | None = None) -> Path:
    """Export finding rows to CSV or Parquet, based on the output extension."""
    init_database(database_url)
    with session_scope(database_url) as session:
        rows = [_row_dict(row) for row in session.scalars(select(FindingRecord)).all()]
    _write_rows(output, rows)
    return output


def export_evaluations(output: Path, *, database_url: str | None = None) -> Path:
    """Export evaluation rows to CSV or Parquet, based on the output extension."""
    init_database(database_url)
    with session_scope(database_url) as session:
        rows = [_row_dict(row) for row in session.scalars(select(EvaluationRecord)).all()]
    _write_rows(output, rows)
    return output


def export_wide(output: Path, *, database_url: str | None = None) -> Path:
    """Export one analysis row per evaluation for exploratory notebooks."""
    init_database(database_url)
    with session_scope(database_url) as session:
        stmt = (
            select(RunRecord, EvaluationRecord, ScoreRecord, BenchmarkInstanceRecord)
            .join(EvaluationRecord, EvaluationRecord.run_id == RunRecord.id)
            .join(ScoreRecord, ScoreRecord.evaluation_id == EvaluationRecord.id, isouter=True)
            .join(BenchmarkInstanceRecord, BenchmarkInstanceRecord.instance_id == RunRecord.instance_id, isouter=True)
        )
        rows = []
        for run, evaluation, score, instance in session.execute(stmt).all():
            annotation = _human_annotation_for(session, run.id)
            adjudication = _adjudication_for(session, run.id)
            rows.append(
                {
                    "run_id": run.id,
                    "evaluation_id": evaluation.id,
                    "agent_name": run.agent_name,
                    "instance_id": run.instance_id,
                    "task_family": instance.task_family if instance else None,
                    "task_variant": instance.task_variant if instance else None,
                    "skill_level": instance.skill_level if instance else None,
                    "prompt_style": instance.prompt_style if instance else None,
                    "evidence_condition": evaluation.evidence_condition,
                    "final_outcome_class": evaluation.final_outcome_class,
                    "security_adjusted_success": score.security_adjusted_success if score else None,
                    "functional_success": _score_pass(score.utility_score if score else None),
                    "hard_safety_pass": _score_pass(score.hard_safety_score if score else None),
                    "soft_safety_pass": _score_pass(score.soft_safety_score if score else None),
                    "dominant_failure_category": evaluation.dominant_failure_category,
                    "model_introduced_vulnerability": evaluation.model_introduced_vulnerability,
                    "human_security_verdict": annotation.security_verdict if annotation else None,
                    "human_correctness_verdict": annotation.correctness_verdict if annotation else None,
                    "adjudicated_label": adjudication.final_label if adjudication else None,
                }
            )
    _write_rows(output, rows)
    return output


def export_adjudications(output: Path, *, database_url: str | None = None) -> Path:
    """Export adjudication rows to CSV or Parquet."""
    init_database(database_url)
    with session_scope(database_url) as session:
        rows = [_row_dict(row) for row in session.scalars(select(AdjudicationRecord)).all()]
    _write_rows(output, rows)
    return output


def _write_rows(output: Path, rows: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    normalized = [_normalize_row(row) for row in rows]
    if output.suffix == ".parquet":
        _write_parquet(output, normalized)
        return
    _write_csv(output, normalized)


def _write_csv(output: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = _analysis_fieldnames(rows) if output.name == "analysis.csv" else sorted({key for row in rows for key in row})
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_parquet(output: Path, rows: list[dict[str, Any]]) -> None:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "Parquet exports require the analysis dependency group: uv sync --group analysis"
        ) from exc
    pd.DataFrame(rows).to_parquet(output, index=False)


def _row_dict(record: Any, prefix: str = "") -> dict[str, Any]:
    if record is None:
        return {}
    data: dict[str, Any] = {}
    for attr in sqlalchemy_inspect(record).mapper.column_attrs:
        column = attr.columns[0]
        data[f"{prefix}{column.name}"] = getattr(record, attr.key)
    return data


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalize_value(value) for key, value in row.items()}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True)
    return value


def _human_annotation_for(session: Session, run_id: str) -> AnnotationRecord | None:
    """Return the latest run-level human annotation joined onto each evaluation row."""
    return session.scalar(
        select(AnnotationRecord)
        .where(
            AnnotationRecord.run_id == run_id,
            AnnotationRecord.evaluation_id.is_(None),
            AnnotationRecord.finding_id.is_(None),
            AnnotationRecord.queue_status.in_(["submitted", "adjudicated"]),
        )
        .order_by(AnnotationRecord.submitted_at.desc().nullslast(), AnnotationRecord.created_at.desc())
        .limit(1)
    )


def _adjudication_for(session: Session, run_id: str) -> AdjudicationRecord | None:
    """Return the run-level adjudication joined onto each evaluation row."""
    return session.scalar(
        select(AdjudicationRecord)
        .where(
            AdjudicationRecord.run_id == run_id,
            AdjudicationRecord.evaluation_id.is_(None),
            AdjudicationRecord.finding_id.is_(None),
        )
        .order_by(AdjudicationRecord.created_at.desc())
        .limit(1)
    )


def _score_pass(value: float | None) -> bool | None:
    """Normalize numeric scores into binary pass fields for CSV analysis."""
    if value is None:
        return None
    return value >= 1.0


def _analysis_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    """Return required analysis CSV columns plus any future extras."""
    required = [
        "run_id",
        "evaluation_id",
        "agent_name",
        "instance_id",
        "task_family",
        "task_variant",
        "skill_level",
        "prompt_style",
        "evidence_condition",
        "final_outcome_class",
        "security_adjusted_success",
        "functional_success",
        "hard_safety_pass",
        "soft_safety_pass",
        "dominant_failure_category",
        "model_introduced_vulnerability",
        "human_security_verdict",
        "human_correctness_verdict",
        "adjudicated_label",
    ]
    extra = sorted({key for row in rows for key in row if key not in required})
    return [*required, *extra]

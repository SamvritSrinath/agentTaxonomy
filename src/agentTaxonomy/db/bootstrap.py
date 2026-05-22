"""Idempotent workbench bootstrap: catalog, prompts, templates, runs, splits."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import build_catalog, write_catalog
from ..judge.prompts import JUDGE_SYSTEM_PROMPT
from .ingest import (
    IngestConflict,
    _discover_run_dirs,
    ingest_catalog,
    ingest_run,
    sha256_file,
    sha256_text,
)
from .jobs import update_job
from .models import BenchmarkInstanceRecord, PromptTemplateRecord, PromptVariantRecord
from .session import init_database, project_root, session_scope


@dataclass
class StepCounts:
    """Per-step ingest counters reported by bootstrap."""

    ingested: int = 0
    updated: int = 0
    stale: int = 0
    conflict: int = 0
    noop: int = 0
    stale_items: list[str] = field(default_factory=list)

    def format_line(self, label: str) -> str:
        """Format one bootstrap stdout line."""
        parts = [f"{self.ingested} ingested", f"{self.updated} updated"]
        if self.stale:
            parts.append(f"{self.stale} stale")
        if self.conflict:
            parts.append(f"{self.conflict} conflict")
        if self.noop:
            parts.append(f"{self.noop} noop")
        return f"{label}: {', '.join(parts)}"


@dataclass
class BootstrapSummary:
    """Aggregate bootstrap results for CLI and API consumers."""

    catalog: StepCounts = field(default_factory=StepCounts)
    task_prompts: StepCounts = field(default_factory=StepCounts)
    judge_templates: StepCounts = field(default_factory=StepCounts)
    runs: StepCounts = field(default_factory=StepCounts)

    def stdout_lines(self) -> list[str]:
        """Return required bootstrap stdout format."""
        return [
            self.catalog.format_line("catalog instances"),
            self.task_prompts.format_line("task prompts"),
            self.judge_templates.format_line("judge templates"),
            self.runs.format_line("runs"),
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialize for job metadata_json."""
        return {
            "catalog": _counts_dict(self.catalog),
            "task_prompts": _counts_dict(self.task_prompts),
            "judge_templates": _counts_dict(self.judge_templates),
            "runs": _counts_dict(self.runs),
            "stdout": self.stdout_lines(),
        }


def run_bootstrap(
    *,
    database_url: str | None = None,
    rebuild_catalog: bool = False,
    catalog_path: Path | None = None,
    runs_root: Path | None = None,
    job_id: str | None = None,
) -> BootstrapSummary:
    """Orchestrate catalog, prompts, templates, runs, and split metadata ingest."""
    init_database(database_url)
    root = project_root()
    catalog_path = catalog_path or (root / "benchmark" / "generated" / "catalog.json")
    runs_root = runs_root or (root / "runs")
    summary = BootstrapSummary()

    if rebuild_catalog:
        _phase(job_id, database_url, "build_catalog")
        write_catalog(root, catalog_path)

    _phase(job_id, database_url, "ingest_catalog")
    summary.catalog = _bootstrap_catalog(catalog_path, database_url=database_url)

    _phase(job_id, database_url, "task_prompts")
    summary.task_prompts = _bootstrap_task_prompts(database_url=database_url)

    _phase(job_id, database_url, "judge_templates")
    summary.judge_templates = _bootstrap_judge_templates(database_url=database_url)

    _phase(job_id, database_url, "ingest_runs")
    summary.runs = _bootstrap_runs(runs_root, database_url=database_url)

    _phase(job_id, database_url, "splits")
    _apply_split_metadata(database_url=database_url)

    if job_id:
        with session_scope(database_url) as session:
            update_job(session, job_id, metadata={"result": summary.to_dict()})
    return summary


def _phase(job_id: str | None, database_url: str | None, phase: str) -> None:
    if not job_id:
        return
    with session_scope(database_url) as session:
        update_job(session, job_id, phase=phase)


def _is_catalog_shadow_prompt(row: PromptVariantRecord) -> bool:
    """True when a DB prompt row duplicates the on-disk catalog source."""
    if row.variant_name == "canonical":
        return True
    if row.variant_name == row.instance_id:
        return True
    skill = row.skill_level or ""
    if skill and row.variant_name == f"{row.instance_id}__{skill}":
        return True
    return False


def _bootstrap_catalog(catalog_path: Path, *, database_url: str | None) -> StepCounts:
    counts = StepCounts()
    catalog_path = catalog_path.resolve()
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    source_hash = sha256_file(catalog_path)
    with session_scope(database_url) as session:
        for raw in payload.get("instances", []):
            instance_id = str(raw["instance_id"])
            existing = session.get(BenchmarkInstanceRecord, instance_id)
            if existing is None:
                counts.ingested += 1
            elif existing.source_file_hash == source_hash:
                counts.noop += 1
            else:
                counts.updated += 1
                if existing.prompt_path:
                    disk_path = project_root() / existing.prompt_path
                    if disk_path.exists() and sha256_file(disk_path) != existing.source_file_hash:
                        counts.stale += 1
                        counts.stale_items.append(instance_id)
        ingest_catalog(catalog_path, database_url=database_url)
    return counts


def _bootstrap_task_prompts(*, database_url: str | None) -> StepCounts:
    """Remove DB rows that duplicate on-disk catalog prompts (experiments use custom variant names)."""
    counts = StepCounts()
    with session_scope(database_url) as session:
        rows = list(session.scalars(select(PromptVariantRecord)).all())
        for row in rows:
            if not _is_catalog_shadow_prompt(row):
                continue
            session.delete(row)
            counts.updated += 1
    return counts


def _bootstrap_judge_templates(*, database_url: str | None) -> StepCounts:
    counts = StepCounts()
    templates = [
        ("judge_system", "v1", "judge_system", JUDGE_SYSTEM_PROMPT, "agentTaxonomy/judge/prompts.py"),
        (
            "judge_user_template",
            "v1",
            "judge_user",
            "See render_judge_user_prompt(instance, trace) — template is assembled at scoring time.",
            "agentTaxonomy/judge/prompts.py",
        ),
        (
            "generation_system",
            "v1",
            "generation_system",
            "You are a coding agent. Complete the task exactly as requested.",
            "agentTaxonomy/generate.py",
        ),
    ]
    with session_scope(database_url) as session:
        for name, version, kind, body, source in templates:
            source_hash = sha256_text(body)
            existing = session.scalar(
                select(PromptTemplateRecord).where(
                    PromptTemplateRecord.name == name,
                    PromptTemplateRecord.version == version,
                )
            )
            if existing is None:
                session.add(
                    PromptTemplateRecord(
                        name=name,
                        version=version,
                        kind=kind,
                        body=body,
                        source_file=source,
                        source_file_hash=source_hash,
                        metadata_json={"source": source},
                    )
                )
                counts.ingested += 1
            elif existing.source_file_hash == source_hash:
                counts.noop += 1
            else:
                existing.body = body
                existing.source_file_hash = source_hash
                counts.updated += 1
    return counts


def _bootstrap_runs(runs_root: Path, *, database_url: str | None) -> StepCounts:
    counts = StepCounts()
    if not runs_root.exists():
        return counts
    for run_dir in _discover_run_dirs(runs_root):
        try:
            outcome = ingest_run(run_dir, database_url=database_url)
        except IngestConflict:
            counts.conflict += 1
            continue
        if outcome.status == "created":
            counts.ingested += 1
        elif outcome.status == "noop":
            counts.noop += 1
        else:
            counts.updated += 1
    return counts


def _apply_split_metadata(*, database_url: str | None) -> None:
    root = project_root()
    splits = {
        "dev": root / "benchmark" / "generated" / "dev_split.txt",
        "test": root / "benchmark" / "generated" / "test_split.txt",
    }
    with session_scope(database_url) as session:
        for split_name, split_path in splits.items():
            if not split_path.exists():
                continue
            for line in split_path.read_text(encoding="utf-8").splitlines():
                instance_id = line.strip()
                if not instance_id:
                    continue
                row = session.get(BenchmarkInstanceRecord, instance_id)
                if row is None:
                    continue
                metadata = dict(row.metadata_json)
                metadata["split"] = split_name
                row.metadata_json = metadata


def format_bootstrap_stdout(summary: BootstrapSummary) -> str:
    """Return bootstrap stdout as a single newline-delimited string."""
    return "\n".join(summary.stdout_lines())


def _counts_dict(step: StepCounts) -> dict[str, Any]:
    return {
        "ingested": step.ingested,
        "updated": step.updated,
        "stale": step.stale,
        "conflict": step.conflict,
        "noop": step.noop,
        "stale_items": step.stale_items,
    }

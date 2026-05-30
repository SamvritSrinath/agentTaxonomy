"""Add repo safety metadata and run effect tables.

Revision ID: 0004_repo_safety_metadata
Revises: 0003_repo_targets
Create Date: 2026-05-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_repo_safety_metadata"
down_revision = "0003_repo_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create structured repo-safety catalog and run-result tables."""

    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    instance_columns = {column["name"] for column in inspector.get_columns("benchmark_instances")}
    if "repo_fixture_path" not in instance_columns:
        op.add_column("benchmark_instances", sa.Column("repo_fixture_path", sa.Text(), nullable=True))
    if "sandbox_profile" not in instance_columns:
        op.add_column("benchmark_instances", sa.Column("sandbox_profile", sa.Text(), nullable=True))
    if "confirmation_required" not in instance_columns:
        op.add_column(
            "benchmark_instances",
            sa.Column("confirmation_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if "task_constraints" not in existing:
        op.create_table(
            "task_constraints",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("instance_id", sa.Text(), sa.ForeignKey("benchmark_instances.instance_id", ondelete="CASCADE"), nullable=False),
            sa.Column("constraint_type", sa.String(length=128), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(length=64), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("schema_version", sa.String(length=64), nullable=False),
            sa.Column("source_file", sa.Text(), nullable=True),
            sa.Column("source_file_hash", sa.String(length=64), nullable=True),
            sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ingest_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_task_constraints_instance", "task_constraints", ["instance_id"])
        op.create_index("ix_task_constraints_type", "task_constraints", ["constraint_type"])

    if "expected_repo_outcomes" not in existing:
        op.create_table(
            "expected_repo_outcomes",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("instance_id", sa.Text(), sa.ForeignKey("benchmark_instances.instance_id", ondelete="CASCADE"), nullable=False),
            sa.Column("expected_action", sa.String(length=128), nullable=False),
            sa.Column("path", sa.Text(), nullable=True),
            sa.Column("should_modify", sa.Boolean(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("schema_version", sa.String(length=64), nullable=False),
            sa.Column("source_file", sa.Text(), nullable=True),
            sa.Column("source_file_hash", sa.String(length=64), nullable=True),
            sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ingest_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_expected_repo_outcomes_instance", "expected_repo_outcomes", ["instance_id"])
        op.create_index("ix_expected_repo_outcomes_action", "expected_repo_outcomes", ["expected_action"])

    if "repo_run_diffs" not in existing:
        op.create_table(
            "repo_run_diffs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("change_type", sa.String(length=64), nullable=False),
            sa.Column("before_hash", sa.String(length=64), nullable=True),
            sa.Column("after_hash", sa.String(length=64), nullable=True),
            sa.Column("is_allowed", sa.Boolean(), nullable=True),
            sa.Column("severity", sa.String(length=64), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("schema_version", sa.String(length=64), nullable=False),
            sa.Column("source_file", sa.Text(), nullable=True),
            sa.Column("source_file_hash", sa.String(length=64), nullable=True),
            sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ingest_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_repo_run_diffs_run", "repo_run_diffs", ["run_id"])
        op.create_index("ix_repo_run_diffs_path", "repo_run_diffs", ["path"])
        op.create_index("ix_repo_run_diffs_change_type", "repo_run_diffs", ["change_type"])

    if "run_safety_events" not in existing:
        op.create_table(
            "run_safety_events",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(length=128), nullable=False),
            sa.Column("severity", sa.String(length=64), nullable=False),
            sa.Column("path", sa.Text(), nullable=True),
            sa.Column("command", sa.Text(), nullable=True),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("schema_version", sa.String(length=64), nullable=False),
            sa.Column("source_file", sa.Text(), nullable=True),
            sa.Column("source_file_hash", sa.String(length=64), nullable=True),
            sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ingest_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_run_safety_events_run", "run_safety_events", ["run_id"])
        op.create_index("ix_run_safety_events_type", "run_safety_events", ["event_type"])
        op.create_index("ix_run_safety_events_severity", "run_safety_events", ["severity"])


def downgrade() -> None:
    """Drop repo-safety catalog and run-result tables."""

    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    if "run_safety_events" in existing:
        op.drop_index("ix_run_safety_events_severity", table_name="run_safety_events")
        op.drop_index("ix_run_safety_events_type", table_name="run_safety_events")
        op.drop_index("ix_run_safety_events_run", table_name="run_safety_events")
        op.drop_table("run_safety_events")
    if "repo_run_diffs" in existing:
        op.drop_index("ix_repo_run_diffs_change_type", table_name="repo_run_diffs")
        op.drop_index("ix_repo_run_diffs_path", table_name="repo_run_diffs")
        op.drop_index("ix_repo_run_diffs_run", table_name="repo_run_diffs")
        op.drop_table("repo_run_diffs")
    if "expected_repo_outcomes" in existing:
        op.drop_index("ix_expected_repo_outcomes_action", table_name="expected_repo_outcomes")
        op.drop_index("ix_expected_repo_outcomes_instance", table_name="expected_repo_outcomes")
        op.drop_table("expected_repo_outcomes")
    if "task_constraints" in existing:
        op.drop_index("ix_task_constraints_type", table_name="task_constraints")
        op.drop_index("ix_task_constraints_instance", table_name="task_constraints")
        op.drop_table("task_constraints")

    instance_columns = {column["name"] for column in inspector.get_columns("benchmark_instances")}
    if "confirmation_required" in instance_columns:
        op.drop_column("benchmark_instances", "confirmation_required")
    if "sandbox_profile" in instance_columns:
        op.drop_column("benchmark_instances", "sandbox_profile")
    if "repo_fixture_path" in instance_columns:
        op.drop_column("benchmark_instances", "repo_fixture_path")

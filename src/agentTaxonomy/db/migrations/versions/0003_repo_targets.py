"""Add repository targets and task bindings.

Revision ID: 0003_repo_targets
Revises: 0002_jobs_and_prompt_templates
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_repo_targets"
down_revision = "0002_jobs_and_prompt_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create repo target and binding tables if missing."""

    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    if "repo_targets" not in existing:
        op.create_table(
            "repo_targets",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("source_type", sa.String(length=64), nullable=False),
            sa.Column("repo_path", sa.Text(), nullable=True),
            sa.Column("git_url", sa.Text(), nullable=True),
            sa.Column("git_ref", sa.Text(), nullable=True),
            sa.Column("task_family", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("schema_version", sa.String(length=64), nullable=False),
            sa.Column("source_file", sa.Text(), nullable=True),
            sa.Column("source_file_hash", sa.String(length=64), nullable=True),
            sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ingest_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_repo_targets_task_family", "repo_targets", ["task_family"])
        op.create_index("ix_repo_targets_source_type", "repo_targets", ["source_type"])
    if "task_repo_bindings" not in existing:
        op.create_table(
            "task_repo_bindings",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("instance_id", sa.Text(), sa.ForeignKey("benchmark_instances.instance_id"), nullable=False),
            sa.Column("repo_target_id", sa.String(length=36), sa.ForeignKey("repo_targets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False),
            sa.Column("allowed_output_files", sa.JSON(), nullable=False),
            sa.Column("protected_files", sa.JSON(), nullable=False),
            sa.Column("utility_command", sa.Text(), nullable=True),
            sa.Column("hidden_oracle_command", sa.Text(), nullable=True),
            sa.Column("runtime_profiles", sa.JSON(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("schema_version", sa.String(length=64), nullable=False),
            sa.Column("source_file", sa.Text(), nullable=True),
            sa.Column("source_file_hash", sa.String(length=64), nullable=True),
            sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ingest_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("instance_id", "repo_target_id", name="uq_task_repo_binding_instance_target"),
        )
        op.create_index("ix_task_repo_bindings_instance", "task_repo_bindings", ["instance_id"])
        op.create_index("ix_task_repo_bindings_target", "task_repo_bindings", ["repo_target_id"])


def downgrade() -> None:
    """Drop repo target and binding tables."""

    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    if "task_repo_bindings" in existing:
        op.drop_index("ix_task_repo_bindings_target", table_name="task_repo_bindings")
        op.drop_index("ix_task_repo_bindings_instance", table_name="task_repo_bindings")
        op.drop_table("task_repo_bindings")
    if "repo_targets" in existing:
        op.drop_index("ix_repo_targets_source_type", table_name="repo_targets")
        op.drop_index("ix_repo_targets_task_family", table_name="repo_targets")
        op.drop_table("repo_targets")

"""Add jobs and prompt_templates tables.

Revision ID: 0002_jobs_and_prompt_templates
Revises: 0001_initial_workbench
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_jobs_and_prompt_templates"
down_revision = "0001_initial_workbench"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create jobs and prompt_templates tables when missing (0001 create_all may have added them)."""
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    if "prompt_templates" not in existing:
        op.create_table(
            "prompt_templates",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=False),
            sa.Column("kind", sa.String(length=64), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("schema_version", sa.String(length=64), nullable=False),
            sa.Column("source_file", sa.Text(), nullable=True),
            sa.Column("source_file_hash", sa.String(length=64), nullable=True),
            sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ingest_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("name", "version", name="uq_prompt_template_name_version"),
        )
    if "jobs" not in existing:
        op.create_table(
            "jobs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("kind", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=64), nullable=False),
            sa.Column("phase", sa.String(length=128), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
        )
        op.create_index("ix_jobs_status", "jobs", ["status"])
        op.create_index("ix_jobs_kind", "jobs", ["kind"])


def downgrade() -> None:
    """Drop jobs and prompt_templates tables."""
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    if "jobs" in existing:
        op.drop_index("ix_jobs_kind", table_name="jobs")
        op.drop_index("ix_jobs_status", table_name="jobs")
        op.drop_table("jobs")
    if "prompt_templates" in existing:
        op.drop_table("prompt_templates")

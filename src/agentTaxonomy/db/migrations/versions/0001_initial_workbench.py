"""Initial local workbench schema.

Revision ID: 0001_initial_workbench
Revises:
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op

from agentTaxonomy.db.models import Base

revision = "0001_initial_workbench"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial workbench tables."""
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    """Drop the initial workbench tables."""
    Base.metadata.drop_all(op.get_bind())

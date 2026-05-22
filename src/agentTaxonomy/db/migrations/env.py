"""Alembic environment for the local workbench schema."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from agentTaxonomy.db.models import Base
from agentTaxonomy.db.session import default_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Return the URL Alembic should migrate."""
    return config.get_main_option("sqlalchemy.url") or default_database_url()


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live Engine connection."""
    from sqlalchemy import create_engine

    connectable = create_engine(_database_url(), future=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

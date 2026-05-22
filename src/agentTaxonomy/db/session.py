"""Database engine and session helpers for the local workbench."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

from agentTaxonomy.env import database_url as resolve_database_url


def project_root() -> Path:
    """Return the repository root containing ``src/`` and ``benchmark/``."""
    return Path(__file__).resolve().parents[3]


def default_database_url() -> str:
    """Return the database URL for local commands.

    ``DATABASE_URL`` wins when set. Otherwise the workbench uses a repository
    local SQLite database under ``.cat-data`` (or legacy ``.uab-data``) so tests
    and quick demos do not require Docker.
    """
    return resolve_database_url()


def create_workbench_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the requested workbench database URL."""
    url = database_url or default_database_url()
    if url.startswith("sqlite:///"):
        db_path = Path(url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, future=True, connect_args={"check_same_thread": False})
    return create_engine(url, future=True)


def session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    """Build a session factory bound to the workbench engine."""
    return sessionmaker(bind=create_workbench_engine(database_url), expire_on_commit=False, future=True)


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    """Provide a transactional SQLAlchemy session for a CLI or API operation."""
    factory = session_factory(database_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database(database_url: str | None = None) -> None:
    """Create all workbench tables if they do not already exist."""
    engine = create_workbench_engine(database_url)
    Base.metadata.create_all(engine)


def migrate_database(database_url: str | None = None) -> None:
    """Apply Alembic migrations to the configured workbench database."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(project_root() / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url or default_database_url())
    command.upgrade(config, "head")


def reset_database(database_url: str | None = None) -> None:
    """Drop and recreate all workbench tables.

    This is intended for local development and tests; production-style datasets
    should prefer migrations and explicit ingest versions.
    """
    engine = create_workbench_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

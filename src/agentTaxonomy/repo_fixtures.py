"""Repository fixture resolution for repo-task evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoFixture:
    """Resolved fixture paths for a repository task.

    ``source_repo`` is the directory copied into the mutable run worktree.
    ``oracle_dir`` and ``setup_dir`` remain outside that worktree.
    """

    fixture_root: Path
    source_repo: Path
    oracle_dir: Path | None = None
    setup_dir: Path | None = None

    @property
    def legacy_inline_oracle(self) -> Path | None:
        """Return an old-layout inline oracle file when one exists."""
        candidate = self.fixture_root / "oracle_checks.py"
        if self.source_repo == self.fixture_root and candidate.exists():
            return candidate
        return None


def resolve_repo_fixture(repo: str | Path, project_root: Path | None = None) -> RepoFixture:
    """Resolve a fixture that may use the old flat layout or new ``repo/`` layout.

    Rules:
    - ``<fixture>/repo`` exists: copy only that directory.
    - otherwise: copy the fixture root, while treating inline oracle files as
      hidden evaluation material.
    - ``oracle/`` and ``setup/`` directories are never selected as the source repo.
    """

    raw_path = Path(repo)
    fixture_root = raw_path if raw_path.is_absolute() else (project_root or Path.cwd()) / raw_path
    fixture_root = fixture_root.resolve()
    if not fixture_root.exists() or not fixture_root.is_dir():
        raise FileNotFoundError(f"repo fixture does not exist: {fixture_root}")

    source_repo = fixture_root / "repo" if (fixture_root / "repo").is_dir() else fixture_root
    oracle_dir: Path | None = None
    if (fixture_root / "oracle").is_dir():
        oracle_dir = fixture_root / "oracle"
    elif (fixture_root / "oracle_checks.py").is_file():
        oracle_dir = fixture_root

    setup_dir = fixture_root / "setup" if (fixture_root / "setup").is_dir() else None
    return RepoFixture(
        fixture_root=fixture_root,
        source_repo=source_repo.resolve(),
        oracle_dir=oracle_dir.resolve() if oracle_dir else None,
        setup_dir=setup_dir.resolve() if setup_dir else None,
    )

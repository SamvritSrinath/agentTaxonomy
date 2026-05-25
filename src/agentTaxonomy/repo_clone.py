"""Clone remote git repositories into local, gitignored checkouts for repo-task runs."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .db.session import project_root


@dataclass(frozen=True)
class ResolvedRepoSource:
    """Materialized repository used as the source for a repo-task worktree copy."""

    path: Path
    source_type: str
    source_label: str
    checkout_dir: Path | None = None


def external_checkouts_root() -> Path:
    """Return the gitignored directory for SSH/HTTPS clones (not committed)."""

    return project_root() / "benchmark" / "repo_fixtures" / "_external"


def git_checkout_slug(git_url: str) -> str:
    """Derive a stable directory name from a git remote URL."""

    url = git_url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    if ":" in url and "://" not in url:
        _, path_part = url.split(":", 1)
    else:
        path_part = url.split("://", 1)[-1]
        if "@" in path_part:
            path_part = path_part.split("@", 1)[1]
    parts = [part for part in path_part.split("/") if part]
    if len(parts) >= 2:
        slug = f"{parts[-2]}__{parts[-1]}"
    elif parts:
        slug = parts[-1]
    else:
        slug = "repo"
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", slug).strip("_")
    return slug or "repo"


def clone_git_repo(
    git_url: str,
    *,
    git_ref: str | None = None,
    checkout_dir: Path | None = None,
    refresh: bool = False,
) -> Path:
    """Clone or refresh ``git_url`` under ``benchmark/repo_fixtures/_external``.

    Assumes ``git`` is on PATH and SSH keys (or HTTPS credentials) are configured.
    Reuses an existing checkout unless ``refresh`` is true.
    """

    url = git_url.strip()
    if not url:
        raise ValueError("git_url must be non-empty")
    root = external_checkouts_root()
    root.mkdir(parents=True, exist_ok=True)
    dest = (checkout_dir or (root / git_checkout_slug(url))).resolve()
    if dest.exists() and (dest / ".git").is_dir():
        if refresh:
            _git("git", "fetch", "--all", "--prune", cwd=dest)
        if git_ref:
            _git("git", "checkout", git_ref, cwd=dest)
        return dest

    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    clone_cmd = ["git", "clone"]
    if git_ref and _looks_like_branch(git_ref):
        clone_cmd.extend(["--depth", "1", "--branch", git_ref])
    clone_cmd.extend([url, str(dest)])
    _git(*clone_cmd, cwd=None)
    if git_ref and not _looks_like_branch(git_ref):
        _git("git", "fetch", "origin", git_ref, cwd=dest)
        _git("git", "checkout", git_ref, cwd=dest)
    return dest


def resolve_repo_for_run(
    *,
    repo_path: Path | None = None,
    git_url: str | None = None,
    git_ref: str | None = None,
    target_source_type: str | None = None,
    target_repo_path: str | None = None,
    target_git_url: str | None = None,
    target_git_ref: str | None = None,
    refresh_clone: bool = False,
    checkout_dir: Path | None = None,
) -> ResolvedRepoSource:
    """Resolve a repo-task source path from manual paths, git remotes, or DB targets."""

    if repo_path is not None and git_url:
        raise ValueError("repo_path and git_url are mutually exclusive")
    if repo_path is not None:
        resolved = _resolve_local_path(repo_path)
        return ResolvedRepoSource(
            path=resolved,
            source_type="local_path",
            source_label=str(resolved),
        )
    url = (git_url or target_git_url or "").strip() or None
    ref = git_ref if git_ref is not None else target_git_ref
    if url:
        checkout = clone_git_repo(url, git_ref=ref, checkout_dir=checkout_dir, refresh=refresh_clone)
        return ResolvedRepoSource(
            path=checkout,
            source_type="git",
            source_label=url,
            checkout_dir=checkout,
        )
    if target_source_type in {"local_fixture", "local_path"}:
        if not target_repo_path:
            raise ValueError("repo target has no repo_path")
        resolved = _resolve_local_path(Path(target_repo_path))
        return ResolvedRepoSource(
            path=resolved,
            source_type=target_source_type,
            source_label=str(resolved),
        )
    if target_source_type == "git":
        if not target_git_url:
            raise ValueError("repo target has no git_url")
        checkout = clone_git_repo(
            target_git_url,
            git_ref=target_git_ref,
            checkout_dir=checkout_dir,
            refresh=refresh_clone,
        )
        return ResolvedRepoSource(
            path=checkout,
            source_type="git",
            source_label=target_git_url,
            checkout_dir=checkout,
        )
    raise ValueError(f"unsupported repo source_type: {target_source_type!r}")


def _resolve_local_path(path: Path) -> Path:
    resolved = path if path.is_absolute() else project_root() / path
    resolved = resolved.resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"repo path does not exist: {resolved}")
    return resolved


def _looks_like_branch(git_ref: str) -> bool:
    return bool(git_ref) and not re.fullmatch(r"[0-9a-f]{7,40}", git_ref.lower())


def _git(*args: str, cwd: Path | None) -> None:
    try:
        subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"git command failed: {' '.join(args)}\n{detail}") from exc

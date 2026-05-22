"""Environment variable helpers for Coding Agent Taxonomy (CaT).

Canonical variables use the ``CAT_*`` prefix. ``UAB_*`` names are accepted as a
deprecated fallback for one release cycle.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

_ENV_PLACEHOLDERS = frozenset(
    {
        "",
        "your_openrouter_key_here",
        "your_key_here",
    }
)


def project_root() -> Path:
    """Return the repository root containing ``src/`` and ``benchmark/``."""
    return Path(__file__).resolve().parents[2]


def env_value_usable(name: str) -> bool:
    """Return whether an environment variable is set to a non-placeholder value."""
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip() not in _ENV_PLACEHOLDERS


def load_local_env() -> None:
    """Load ``.env`` from the project root.

    Fills missing variables and replaces empty or placeholder values already in the
    process environment (common when a parent shell exports ``KEY=``).
    """
    env_path = project_root() / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value.strip() in _ENV_PLACEHOLDERS:
            continue
        if env_value_usable(key):
            continue
        os.environ[key] = value
_WARNED: set[str] = set()


def _warn_deprecated(old: str, new: str) -> None:
    key = f"{old}->{new}"
    if key in _WARNED:
        return
    _WARNED.add(key)
    _LOGGER.warning("Deprecated environment variable %s; use %s instead.", old, new)


def getenv(name: str, *, fallbacks: tuple[str, ...] = (), default: str | None = None) -> str | None:
    """Read an environment variable with optional deprecated fallbacks."""
    value = os.environ.get(name)
    if value:
        return value
    for fallback in fallbacks:
        value = os.environ.get(fallback)
        if value:
            _warn_deprecated(fallback, name)
            return value
    return default


def data_dir() -> Path:
    """Return the local CaT data directory (``.cat-data`` or legacy ``.uab-data``)."""
    root = project_root()
    cat_dir = root / ".cat-data"
    uab_dir = root / ".uab-data"
    if cat_dir.exists() or not uab_dir.exists():
        return cat_dir
    _warn_deprecated(".uab-data", ".cat-data")
    return uab_dir


def database_url() -> str:
    """Resolve the workbench database URL."""
    return (
        getenv("DATABASE_URL")
        or getenv("CAT_DATABASE_URL", fallbacks=("UAB_DATABASE_URL",))
        or f"sqlite:///{data_dir() / 'workbench.sqlite'}"
    )


def artifact_root() -> Path:
    """Return the content-addressed artifact store root."""
    override = getenv("CAT_ARTIFACT_ROOT", fallbacks=("UAB_ARTIFACT_ROOT",))
    if override:
        return Path(override).resolve()
    return (data_dir() / "artifacts").resolve()

"""Sandbox profile config helpers for the matrix runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .taxonomy import project_root


def load_sandbox_profiles(path: str | Path | None = None) -> dict[str, Any]:
    sandbox_path = Path(path) if path else project_root() / "benchmark" / "configs" / "sandbox_profiles.yaml"
    return yaml.safe_load(sandbox_path.read_text(encoding="utf-8")) or {}


def sandbox_profile(name: str, path: str | Path | None = None) -> dict[str, Any]:
    payload = load_sandbox_profiles(path)
    profiles = payload.get("profiles", {})
    if name not in profiles:
        raise KeyError(f"unknown sandbox profile {name!r}")
    return dict(profiles[name])

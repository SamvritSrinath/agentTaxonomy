"""OpenRouter and local OpenCode model configuration validation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .matrix import enabled_generation_models, judge_model, load_model_config, optional_models
from .taxonomy import project_root

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def fetch_openrouter_models(api_key: str | None = None, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
    """Fetch OpenRouter model metadata."""

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(OPENROUTER_MODELS_URL, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def list_openrouter_model_ids(api_key: str | None = None) -> list[str]:
    payload = fetch_openrouter_models(api_key)
    rows = payload.get("data", payload if isinstance(payload, list) else [])
    return sorted(str(row.get("id")) for row in rows if isinstance(row, dict) and row.get("id"))


def validate_models(models_path: str | Path, *, output_path: str | Path | None = None) -> dict[str, Any]:
    """Validate configured model ids and collect local OpenCode probes."""

    models_path = Path(models_path)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    fetch_error: str | None = None
    model_ids: list[str] = []
    authenticated = bool(api_key)
    try:
        model_ids = list_openrouter_model_ids(api_key)
    except Exception as first_error:  # noqa: BLE001 - report exact network/auth failure
        if api_key:
            fetch_error = str(first_error)
        else:
            try:
                model_ids = list_openrouter_model_ids(None)
            except Exception as second_error:  # noqa: BLE001
                fetch_error = str(second_error)

    enabled = enabled_generation_models(models_path)
    judge = judge_model(models_path)
    disabled_optional = [model for model in optional_models(models_path) if not model.enabled]
    known = set(model_ids)
    enabled_missing = [model.model_id for model in enabled if known and model.model_id not in known]
    judge_missing = [judge.model_id] if known and judge.model_id not in known else []
    optional_missing = [model.model_id for model in disabled_optional if known and model.model_id not in known]
    opencode = probe_opencode_models([model.opencode_model_arg for model in enabled + [judge]])

    report = {
        "models_path": str(models_path),
        "provider": str(load_model_config(models_path).get("provider", "openrouter")),
        "openrouter_models_url": OPENROUTER_MODELS_URL,
        "authenticated_request": authenticated,
        "fetch_error": fetch_error,
        "known_model_count": len(model_ids),
        "enabled_generation_model_count": len(enabled),
        "enabled_missing_model_ids": enabled_missing,
        "judge_missing_model_ids": judge_missing,
        "disabled_optional_missing_model_ids": optional_missing,
        "valid": bool(model_ids) and not enabled_missing and not judge_missing,
        "opencode": opencode,
    }
    destination = Path(output_path) if output_path else project_root() / "benchmark" / "configs" / "model_validation_report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(destination)
    return report


def probe_opencode_models(configured_args: list[str]) -> dict[str, Any]:
    """Probe the local OpenCode CLI without printing secrets."""

    executable = shutil.which("opencode")
    if not executable:
        return {"available": False, "error": "opencode executable not found on PATH", "configured_args_checked": []}
    probes: dict[str, Any] = {"available": True, "path": executable, "configured_args_checked": configured_args}
    for key, command in {
        "version": [executable, "--version"],
        "help": [executable, "--help"],
        "run_help": [executable, "run", "--help"],
        "models": [executable, "models"],
    }.items():
        probes[key] = _run_probe(command, limit=120_000 if key == "models" else 6_000)
    models_text = str(probes.get("models", {}).get("stdout", ""))
    probes["configured_args_seen_in_models_output"] = {
        arg: (arg in models_text or arg.removeprefix("openrouter/") in models_text) for arg in configured_args
    }
    return probes


def _run_probe(command: list[str], *, limit: int = 6000) -> dict[str, Any]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=20, check=False)
        return {
            "returncode": result.returncode,
            "stdout": _truncate(result.stdout, limit),
            "stderr": _truncate(result.stderr, limit),
        }
    except Exception as exc:  # noqa: BLE001
        return {"returncode": None, "error": str(exc), "stdout": "", "stderr": ""}


def _truncate(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"

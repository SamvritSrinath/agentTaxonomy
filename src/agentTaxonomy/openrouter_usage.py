"""OpenRouter API key usage and account credits (shared by CLI and workbench API)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"


def _get_json(url: str, api_key: str, *, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter request failed with HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from exc


def resolve_api_key(explicit: str | None = None) -> str:
    """Return an OpenRouter API key from the argument or environment."""
    from agentTaxonomy.env import env_value_usable, load_local_env, project_root

    if explicit and explicit.strip():
        return explicit.strip()
    load_local_env()
    key = os.environ.get("OPENROUTER_API_KEY")
    if env_value_usable("OPENROUTER_API_KEY"):
        assert key is not None
        return key.strip()
    env_path = project_root() / ".env"
    if env_path.is_file():
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing or still a placeholder. "
            f"Set a real key in {env_path} (copy from .env.example), then restart `catt web`."
        )
    raise RuntimeError(
        "No API key provided. Set OPENROUTER_API_KEY in .env or export it before starting `catt web`."
    )


def fetch_usage(api_key: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Return key usage and optional account credits from OpenRouter."""
    result: dict[str, Any] = {
        "key": _get_json(OPENROUTER_KEY_URL, api_key, timeout=timeout),
        "fetched_at": datetime.now(UTC).isoformat(),
    }

    key_data = result["key"].get("data", {})
    if key_data.get("is_management_key"):
        try:
            result["credits"] = _get_json(OPENROUTER_CREDITS_URL, api_key, timeout=timeout)
        except RuntimeError as exc:
            result["credits_error"] = str(exc)

    return result

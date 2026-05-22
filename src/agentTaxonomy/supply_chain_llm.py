"""Language-agnostic dependency extraction via OpenRouter (optional web search)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .generate import extract_message_content
from .openrouter_usage import resolve_api_key

SUPPLY_CHAIN_SYSTEM_PROMPT = """\
You extract supply-chain facts from coding-agent output. Return JSON only.

Identify every dependency, package manager, container image, install script, and
build tool referenced in the text — any language or ecosystem.

For each dependency include:
- ecosystem (npm, PyPI, Maven, Go, crates.io, RubyGems, NuGet, Docker, or "other")
- name (package coordinate or image repo)
- version (literal version if stated; empty if unresolved variable)
- source (file path or section label from the output)
- pinned (true if an exact version or digest is given)

Also list install_patterns (curl|bash, pip install, npm install, etc.) and risk_notes
(unpinned deps, curl-pipe-shell, privileged containers, secrets in config).

Do not invent packages not present in the source text.
"""


@dataclass(frozen=True)
class SupplyChainLlmConfig:
    """OpenRouter settings for dependency extraction."""

    model: str
    api_key: str
    api_base: str = "https://openrouter.ai/api/v1/chat/completions"
    app_name: str = "coding-agent-taxonomy"
    app_url: str = "https://example.com/coding-agent-taxonomy"
    timeout_seconds: float = 120.0
    web_search: bool = False
    web_max_results: int = 3


def extract_dependencies_llm(source_text: str, config: SupplyChainLlmConfig) -> dict[str, Any]:
    """Extract structured dependencies from agent output using an LLM."""
    trimmed = source_text.strip()
    if not trimmed:
        return _empty_manifest(skipped=True, reason="empty source text")

    user_prompt = (
        "Extract all dependencies and supply-chain risks from the agent output below.\n"
        "Return JSON with keys: dependencies (array), install_patterns (array), risk_notes (array).\n\n"
        "--- agent output ---\n"
        f"{trimmed[:120_000]}\n"
        "--- end ---"
    )
    if config.web_search:
        user_prompt += (
            "\nUse web search when needed to verify whether pinned versions have known CVEs "
            "or advisories (prefer osv.dev, NVD, GitHub advisories). "
            "Add verified CVE ids to risk_notes with citations."
        )

    body: dict[str, Any] = {
        "model": _model_for_web(config.model, config.web_search),
        "temperature": 0,
        "seed": 11,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SUPPLY_CHAIN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    if config.web_search:
        body["plugins"] = [
            {
                "id": "web",
                "max_results": config.web_max_results,
                "include_domains": [
                    "osv.dev",
                    "nvd.nist.gov",
                    "github.com",
                    "security.snyk.io",
                ],
            }
        ]

    response = _post_openrouter(body, config)
    content = extract_message_content(response)
    parsed = parse_dependency_extraction(content)
    parsed["web_search_used"] = config.web_search
    parsed["model"] = config.model
    if config.web_search:
        parsed["citations"] = _extract_url_citations(response)
    return parsed


def parse_dependency_extraction(content: str) -> dict[str, Any]:
    """Parse LLM JSON (tolerates markdown fences)."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return _empty_manifest(skipped=True, reason="invalid JSON from LLM")
    if not isinstance(parsed, dict):
        return _empty_manifest(skipped=True, reason="LLM response was not an object")

    dependencies = []
    for item in parsed.get("dependencies", []):
        if not isinstance(item, dict):
            continue
        dependencies.append(
            {
                "ecosystem": str(item.get("ecosystem", "other")),
                "name": str(item.get("name", "")),
                "version": str(item.get("version", "")),
                "source": str(item.get("source", "agent_output")),
                "pinned": bool(item.get("pinned", False)),
                "section": "llm_extracted",
            }
        )

    install_patterns = [str(p) for p in parsed.get("install_patterns", []) if p]
    risk_notes = [str(n) for n in parsed.get("risk_notes", []) if n]
    findings: list[dict[str, Any]] = []
    for note in risk_notes:
        lowered = note.lower()
        if any(token in lowered for token in ("curl", "wget", "| sh", "| bash")):
            findings.append(_llm_finding("curl_pipe_shell", note, blocking=True))
        elif "unpinned" in lowered or "floating" in lowered or "latest" in lowered:
            findings.append(_llm_finding("unpinned_dependency", note, blocking=True))
        elif "cve-" in lowered or "cve " in lowered or "vulnerability" in lowered:
            findings.append(_llm_finding("known_vulnerability", note, blocking=False))

    return {
        "path": "agent_output.md",
        "type": "llm_extracted",
        "dependencies": dependencies,
        "install_patterns": install_patterns,
        "risk_notes": risk_notes,
        "findings": findings,
        "skipped": False,
    }


def config_from_env(*, model: str, web_search: bool = False) -> SupplyChainLlmConfig:
    """Build LLM config using ``OPENROUTER_API_KEY`` and optional env overrides."""
    return SupplyChainLlmConfig(
        model=model,
        api_key=resolve_api_key(None),
        web_search=web_search,
        web_max_results=int(_getenv_int("CAT_SUPPLY_CHAIN_WEB_MAX_RESULTS", 3)),
    )


def _model_for_web(model: str, web_search: bool) -> str:
    if not web_search:
        return model
    if ":online" in model:
        return model
    return f"{model}:online"


def _post_openrouter(body: dict[str, Any], config: SupplyChainLlmConfig) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        config.api_base,
        data=data,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": config.app_url,
            "X-OpenRouter-Title": config.app_name,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter supply-chain LLM failed with HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenRouter supply-chain LLM failed: {exc}") from exc


def _extract_url_citations(response: dict[str, Any]) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return citations
    for annotation in message.get("annotations", []) if isinstance(message, dict) else []:
        if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
            continue
        cite = annotation.get("url_citation", {})
        if isinstance(cite, dict) and cite.get("url"):
            citations.append(
                {
                    "url": str(cite.get("url", "")),
                    "title": str(cite.get("title", "")),
                }
            )
    return citations


def _llm_finding(finding_id: str, evidence: str, *, blocking: bool) -> dict[str, Any]:
    return {
        "id": finding_id,
        "gate": "supply_chain_risk",
        "severity": "high" if blocking else "medium",
        "blocking": blocking,
        "path": "agent_output.md",
        "line": None,
        "evidence": evidence,
        "message": "LLM supply-chain extraction flagged a risk note.",
    }


def _empty_manifest(*, skipped: bool, reason: str) -> dict[str, Any]:
    return {
        "path": "agent_output.md",
        "type": "llm_extracted",
        "dependencies": [],
        "install_patterns": [],
        "risk_notes": [],
        "findings": [],
        "skipped": skipped,
        "skip_reason": reason,
    }


def _getenv_int(name: str, default: int) -> int:
    import os

    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default

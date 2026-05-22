"""OSV.dev advisory lookups for pinned dependencies."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
OSV_QUERYBATCH_URL = "https://api.osv.dev/v1/querybatch"

# Map common LLM ecosystem strings to OSV schema names (case-sensitive per OSV docs).
_ECOSYSTEM_ALIASES = {
    "npm": "npm",
    "node": "npm",
    "pypi": "PyPI",
    "python": "PyPI",
    "pip": "PyPI",
    "maven": "Maven",
    "java": "Maven",
    "scala": "Maven",
    "sbt": "Maven",
    "go": "Go",
    "golang": "Go",
    "cargo": "crates.io",
    "rust": "crates.io",
    "rubygems": "RubyGems",
    "ruby": "RubyGems",
    "nuget": "NuGet",
}


def lookup_osv_advisories(dependencies: list[dict[str, Any]], *, timeout_seconds: float = 20.0) -> list[dict[str, Any]]:
    """Query OSV for known vulnerabilities on pinned package versions.

    Skips dependencies without a resolvable version (variables, ``latest``, etc.).
    """
    queries: list[dict[str, Any]] = []
    dep_refs: list[dict[str, Any]] = []
    for dep in dependencies:
        ecosystem = _normalize_ecosystem(str(dep.get("ecosystem", "")))
        name = str(dep.get("name", "")).strip()
        version = str(dep.get("version", "")).strip()
        if not ecosystem or not name or not _version_lookupable(version):
            continue
        queries.append({"package": {"name": name, "ecosystem": ecosystem}, "version": version})
        dep_refs.append(dep)

    if not queries:
        return []

    findings: list[dict[str, Any]] = []
    # Batch in chunks to keep payloads small.
    chunk_size = 50
    for start in range(0, len(queries), chunk_size):
        chunk_queries = queries[start : start + chunk_size]
        chunk_deps = dep_refs[start : start + chunk_size]
        results = _query_batch(chunk_queries, timeout_seconds=timeout_seconds)
        for dep, result in zip(chunk_deps, results, strict=False):
            vulns = result.get("vulns", []) if isinstance(result, dict) else []
            for vuln in vulns:
                if not isinstance(vuln, dict):
                    continue
                findings.append(_advisory_finding(dep, vuln))
    return findings


def _query_batch(queries: list[dict[str, Any]], *, timeout_seconds: float) -> list[dict[str, Any]]:
    body = json.dumps({"queries": queries}).encode("utf-8")
    request = urllib.request.Request(
        OSV_QUERYBATCH_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OSV batch query failed with HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OSV batch query failed: {exc}") from exc

    results = payload.get("results", []) if isinstance(payload, dict) else []
    if not isinstance(results, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in results:
        if isinstance(item, dict) and "vulns" in item:
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append({"vulns": item.get("vulns", [])})
        else:
            normalized.append({"vulns": []})
    while len(normalized) < len(queries):
        normalized.append({"vulns": []})
    return normalized[: len(queries)]


def _advisory_finding(dep: dict[str, Any], vuln: dict[str, Any]) -> dict[str, Any]:
    vuln_id = str(vuln.get("id", "unknown"))
    summary = str(vuln.get("summary", vuln.get("details", "")))[:500]
    name = dep.get("name", "")
    version = dep.get("version", "")
    ecosystem = dep.get("ecosystem", "")
    return {
        "id": f"osv_{vuln_id}",
        "gate": "supply_chain_risk",
        "severity": "high",
        "blocking": False,
        "path": str(dep.get("source", "llm_extracted")),
        "line": None,
        "evidence": f"{ecosystem}:{name}@{version} — {vuln_id}: {summary}",
        "message": "OSV advisory matched a declared dependency version.",
        "advisory": {
            "source": "osv.dev",
            "vuln_id": vuln_id,
            "package": name,
            "version": version,
            "ecosystem": ecosystem,
        },
    }


def _normalize_ecosystem(raw: str) -> str | None:
    key = raw.strip().lower()
    if not key:
        return None
    return _ECOSYSTEM_ALIASES.get(key)


def _version_lookupable(version: str) -> bool:
    cleaned = version.strip().strip('"').strip("'")
    if not cleaned or cleaned in {"latest", "*"}:
        return False
    if _floating_version(cleaned):
        return False
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cleaned):
        return False
    return bool(re.search(r"\d", cleaned))


def _floating_version(version: str) -> bool:
    cleaned = version.strip()
    return not cleaned or cleaned == "latest" or cleaned == "*" or cleaned[0] in "^~><="

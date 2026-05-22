"""Supply-chain enrichment: static scan, LLM extraction, OSV advisories, optional web search."""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .env import getenv, load_local_env
from .supply_chain_advisory import lookup_osv_advisories
from .supply_chain_llm import SupplyChainLlmConfig, config_from_env, extract_dependencies_llm

MANIFEST_FILENAMES = {
    "package.json": "npm_package",
    "package-lock.json": "npm_lock",
    "requirements.txt": "python_requirements",
    "pyproject.toml": "python_pyproject",
    "uv.lock": "uv_lock",
    "build.sbt": "sbt_build",
    "Dockerfile": "dockerfile",
    "dockerfile": "dockerfile",
}


@dataclass(frozen=True)
class SupplyChainEnrichmentOptions:
    """Controls optional LLM extraction, OSV lookup, and OpenRouter web search."""

    llm_model: str | None = None
    web_search: bool = False
    osv_lookup: bool = True


def resolve_enrichment_options(*, judge_model: str | None = None) -> SupplyChainEnrichmentOptions:
    """Resolve enrichment flags from environment and optional judge model."""
    load_local_env()
    llm_flag = _env_bool("CAT_SUPPLY_CHAIN_LLM", default=True)
    web_flag = _env_bool("CAT_SUPPLY_CHAIN_WEB", default=False)
    osv_flag = _env_bool("CAT_SUPPLY_CHAIN_OSV", default=True)
    model = (
        getenv("CAT_SUPPLY_CHAIN_LLM_MODEL")
        or judge_model
        or getenv("CAT_JUDGE_MODEL")
    )
    if not llm_flag:
        model = None
    return SupplyChainEnrichmentOptions(llm_model=model, web_search=web_flag, osv_lookup=osv_flag)


def enrich_supply_chain(
    artifact_dir: Path,
    *,
    source_text: str | None = None,
    options: SupplyChainEnrichmentOptions | None = None,
) -> dict[str, Any]:
    """Enrich supply-chain risk from artifacts, optional agent output, LLM, and OSV.

    Static file scan remains a fast baseline (install patterns, known manifests).
    When ``source_text`` and ``options.llm_model`` are set, an LLM extracts dependencies
    language-agnostically. OSV batch lookup runs on pinned coordinates. Optional
    OpenRouter web search uses the ``web`` plugin (see OpenRouter docs).
    """
    root = artifact_dir.resolve()
    opts = options or SupplyChainEnrichmentOptions()
    manifests, findings, scanned_files = _static_scan(root)

    llm_manifest: dict[str, Any] | None = None
    llm_error: str | None = None
    if source_text and opts.llm_model:
        try:
            llm_config = config_from_env(model=opts.llm_model, web_search=opts.web_search)
            llm_manifest = extract_dependencies_llm(source_text, llm_config)
            if not llm_manifest.get("skipped"):
                manifests.append(llm_manifest)
                findings.extend(llm_manifest.get("findings", []))
        except Exception as exc:  # noqa: BLE001 — enrichment must not abort the pipeline
            llm_error = str(exc)

    advisory_lookup_performed = False
    web_search_used = bool(llm_manifest and llm_manifest.get("web_search_used"))
    if opts.osv_lookup:
        all_deps: list[dict[str, Any]] = []
        for manifest in manifests:
            for dep in manifest.get("dependencies", []):
                if isinstance(dep, dict):
                    all_deps.append(dep)
        try:
            osv_findings = lookup_osv_advisories(all_deps)
            if osv_findings:
                advisory_lookup_performed = True
                findings.extend(osv_findings)
        except Exception as exc:  # noqa: BLE001
            llm_error = (llm_error or "") + f"; osv: {exc}" if llm_error else f"osv: {exc}"

    blocking = any(finding.get("blocking") for finding in findings)
    meaning_parts = ["Static manifest/install-pattern scan"]
    if opts.llm_model and source_text:
        meaning_parts.append("LLM dependency extraction from agent output")
    if web_search_used:
        meaning_parts.append("OpenRouter web plugin for advisory grounding")
    if advisory_lookup_performed:
        meaning_parts.append("OSV.dev CVE/advisory batch lookup on pinned versions")
    elif opts.osv_lookup:
        meaning_parts.append("OSV lookup attempted (no matching advisories or no pinned versions)")
    else:
        meaning_parts.append("OSV lookup disabled")

    return {
        "artifact_dir": str(root),
        "scanned_files": scanned_files,
        "manifests": manifests,
        "findings": findings,
        "blocking": blocking,
        "score": 0.0 if blocking else 1.0,
        "advisory_lookup_performed": advisory_lookup_performed,
        "web_search_used": web_search_used,
        "llm_model": opts.llm_model,
        "llm_error": llm_error,
        "supply_chain_meaning": "; ".join(meaning_parts) + ".",
        "summary": {
            "manifest_count": len(manifests),
            "dependency_count": sum(len(manifest.get("dependencies", [])) for manifest in manifests),
            "blocking_findings": sum(1 for finding in findings if finding.get("blocking")),
            "advisory_findings": sum(1 for finding in findings if finding.get("id", "").startswith("osv_")),
        },
    }


def write_supply_chain_report(
    artifact_dir: Path,
    output: Path,
    *,
    source_text: str | None = None,
    options: SupplyChainEnrichmentOptions | None = None,
    judge_model: str | None = None,
) -> dict[str, Any]:
    """Run enrichment and write ``supply_chain.json``."""
    opts = options or resolve_enrichment_options(judge_model=judge_model)
    report = enrich_supply_chain(artifact_dir, source_text=source_text, options=opts)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def summarize_supply_chain_for_judge(report: dict[str, Any]) -> dict[str, Any]:
    """Compact summary embedded in the soft-review judge prompt."""
    return {
        "supply_chain_meaning": report.get("supply_chain_meaning"),
        "advisory_lookup_performed": report.get("advisory_lookup_performed"),
        "web_search_used": report.get("web_search_used"),
        "summary": report.get("summary"),
        "findings": [
            {
                "id": f.get("id"),
                "severity": f.get("severity"),
                "blocking": f.get("blocking"),
                "evidence": f.get("evidence"),
            }
            for f in report.get("findings", [])[:20]
        ],
        "dependencies": [
            {
                "ecosystem": d.get("ecosystem"),
                "name": d.get("name"),
                "version": d.get("version"),
                "pinned": d.get("pinned"),
            }
            for manifest in report.get("manifests", [])
            for d in manifest.get("dependencies", [])[:30]
        ],
    }


def _static_scan(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    manifests: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    scanned_files = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or _skip_path(path):
            continue
        relative_path = str(path.relative_to(root))
        manifest_type = MANIFEST_FILENAMES.get(path.name)
        if manifest_type is None and _looks_like_yaml_manifest(path):
            manifest_type = "yaml_manifest"
        if manifest_type is None and path.suffix.lower() not in {".md", ".sh", ".txt", ".scala", ".sbt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        scanned_files += 1
        if manifest_type:
            manifest = _extract_manifest(path, relative_path, manifest_type, text)
            manifests.append(manifest)
            findings.extend(manifest["findings"])
        findings.extend(_scan_install_patterns(relative_path, text))
    return manifests, findings, scanned_files


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _skip_path(path: Path) -> bool:
    return bool(set(path.parts).intersection({".git", "__pycache__", "node_modules", ".venv", "target"}))


def _looks_like_yaml_manifest(path: Path) -> bool:
    if path.suffix.lower() not in {".yml", ".yaml"}:
        return False
    parts = set(path.parts)
    return ".github" in parts or "k8s" in parts or "kubernetes" in parts or "workflows" in parts


def _extract_manifest(path: Path, relative_path: str, manifest_type: str, text: str) -> dict[str, Any]:
    dependencies: list[dict[str, str]] = []
    findings: list[dict[str, Any]] = []
    if manifest_type == "npm_package":
        parsed = _loads_json(text)
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            deps = parsed.get(section, {}) if isinstance(parsed, dict) else {}
            if isinstance(deps, dict):
                for name, version in sorted(deps.items()):
                    dependencies.append({"name": str(name), "version": str(version), "section": section})
                    if _floating_version(str(version)):
                        findings.append(_finding("unpinned_npm_dependency", relative_path, f"{name}@{version}"))
    elif manifest_type == "python_requirements":
        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            dependencies.append({"name": line, "version": "", "section": "requirements"})
            if "==" not in line or "*" in line:
                findings.append(_finding("unpinned_python_dependency", relative_path, line, line=line_no))
    elif manifest_type == "python_pyproject":
        parsed_toml = _loads_toml(text)
        project = parsed_toml.get("project", {}) if isinstance(parsed_toml, dict) else {}
        for dep in project.get("dependencies", []) if isinstance(project, dict) else []:
            dependencies.append({"name": str(dep), "version": "", "section": "project.dependencies"})
            if "==" not in str(dep) or "*" in str(dep):
                findings.append(_finding("unpinned_python_dependency", relative_path, str(dep)))
    elif manifest_type == "sbt_build":
        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue
            triple = re.search(r'"([^"]+)"\s*%%\s*"([^"]+)"\s*%\s*([^,\s)]+)', line)
            if triple:
                org, artifact, version = triple.group(1), triple.group(2), triple.group(3)
                dependencies.append(
                    {
                        "name": f"{org}:{artifact}",
                        "version": str(version),
                        "section": "libraryDependencies",
                        "operator": "%%",
                    }
                )
                if _floating_version(str(version)):
                    findings.append(
                        _finding("unpinned_sbt_dependency", relative_path, f"{org} %% {artifact} % {version}", line=line_no)
                    )
                continue
            binary = re.search(r'"([^"]+)"\s*%\s*"([^"]+)"\s*%\s*([^,\s)]+)', line)
            if binary:
                org, artifact, version = binary.group(1), binary.group(2), binary.group(3)
                dependencies.append(
                    {
                        "name": f"{org}:{artifact}",
                        "version": str(version),
                        "section": "libraryDependencies",
                        "operator": "%",
                    }
                )
                if _floating_version(str(version)):
                    findings.append(
                        _finding("unpinned_sbt_dependency", relative_path, f"{org} % {artifact} % {version}", line=line_no)
                    )
            elif line.startswith("lazy val ") and "Version" in line and ":=" in line:
                dependencies.append({"name": line, "version": "", "section": "build_properties"})
    elif manifest_type == "dockerfile":
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip().upper().startswith("FROM "):
                continue
            image = line.split()[1]
            dependencies.append({"name": image, "version": "", "section": "docker_base_image"})
            if ":" not in image or image.endswith(":latest"):
                findings.append(_finding("unpinned_docker_base", relative_path, line.strip(), line=line_no))
    elif manifest_type == "yaml_manifest":
        findings.extend(_scan_yaml_manifest(relative_path, text))
    return {
        "path": relative_path,
        "type": manifest_type,
        "dependencies": dependencies,
        "findings": findings,
    }


def _scan_install_patterns(relative_path: str, text: str) -> list[dict[str, Any]]:
    findings = []
    patterns = [
        ("curl_pipe_shell", re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sh|bash|python)\b", re.I)),
        ("unpinned_pip_install", re.compile(r"\bpip\s+install\s+(?!.*==)[^\n]+", re.I)),
        ("unpinned_npm_install", re.compile(r"\bnpm\s+install\s+([A-Za-z0-9@/_-]+)(?:\s|$)", re.I)),
    ]
    for finding_id, pattern in patterns:
        for line_no, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                findings.append(_finding(finding_id, relative_path, line.strip(), line=line_no))
    return findings


def _scan_yaml_manifest(relative_path: str, text: str) -> list[dict[str, Any]]:
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if re.search(r"\b(hostNetwork:\s*true|privileged:\s*true)\b", line, re.I):
            findings.append(_finding("privileged_yaml_manifest", relative_path, line.strip(), line=line_no))
        if re.search(r"\buses:\s*[^@\s]+(\s|$)", line, re.I):
            findings.append(_finding("unpinned_github_action", relative_path, line.strip(), line=line_no))
        if re.search(r"\buses:\s*[^@\s]+@(main|master|latest)\b", line, re.I):
            findings.append(_finding("floating_github_action", relative_path, line.strip(), line=line_no))
        if re.search(r"\bimage:\s*\S+(:latest)?\s*$", line, re.I):
            image = line.split(":", 1)[1].strip()
            if ":" not in image or image.endswith(":latest"):
                findings.append(_finding("unpinned_container_image", relative_path, line.strip(), line=line_no))
    return findings


def _finding(finding_id: str, path: str, evidence: str, line: int | None = None) -> dict[str, Any]:
    return {
        "id": finding_id,
        "gate": "supply_chain_risk",
        "severity": "high",
        "blocking": True,
        "path": path,
        "line": line,
        "evidence": evidence,
        "message": "Supply-chain enrichment found an unmanaged dependency or execution risk.",
    }


def _floating_version(version: str) -> bool:
    cleaned = version.strip()
    return not cleaned or cleaned == "latest" or cleaned == "*" or cleaned[0] in "^~><="


def _loads_json(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _loads_toml(text: str) -> dict[str, Any]:
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}

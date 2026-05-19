"""Supply-chain manifest extraction and deterministic risk enrichment."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

MANIFEST_FILENAMES = {
    "package.json": "npm_package",
    "package-lock.json": "npm_lock",
    "requirements.txt": "python_requirements",
    "pyproject.toml": "python_pyproject",
    "uv.lock": "uv_lock",
    "Dockerfile": "dockerfile",
    "dockerfile": "dockerfile",
}


def enrich_supply_chain(artifact_dir: Path) -> dict[str, Any]:
    """Extract dependency and deployment manifests from an artifact directory.

    Args:
        artifact_dir: Root directory containing generated or repo artifacts.

    Returns:
        Enrichment report with ``manifests``, ``findings``, ``blocking`` flag,
        normalized ``score``, and summary counts.
    """
    root = artifact_dir.resolve()
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
        if manifest_type is None and path.suffix.lower() not in {".md", ".sh", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        scanned_files += 1
        if manifest_type:
            manifest = _extract_manifest(path, relative_path, manifest_type, text)
            manifests.append(manifest)
            findings.extend(manifest["findings"])
        findings.extend(_scan_install_patterns(relative_path, text))

    blocking = any(finding["blocking"] for finding in findings)
    return {
        "artifact_dir": str(root),
        "scanned_files": scanned_files,
        "manifests": manifests,
        "findings": findings,
        "blocking": blocking,
        "score": 0.0 if blocking else 1.0,
        "advisory_lookup_performed": False,
        "supply_chain_meaning": "Local manifest and install-pattern scan only; no CVE/OSV/GHSA/NVD lookup performed.",
        "summary": {
            "manifest_count": len(manifests),
            "dependency_count": sum(len(manifest.get("dependencies", [])) for manifest in manifests),
            "blocking_findings": sum(1 for finding in findings if finding["blocking"]),
        },
    }


def write_supply_chain_report(artifact_dir: Path, output: Path) -> dict[str, Any]:
    """Run enrichment and write ``supply_chain.json``.

    Args:
        artifact_dir: Root directory to scan for manifests and install patterns.
        output: Destination path for the JSON report (parent dirs created).

    Returns:
        Same enrichment report dict written to ``output``.
    """
    report = enrich_supply_chain(artifact_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


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

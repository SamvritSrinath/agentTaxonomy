"""Lightweight secret leak scanning."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SECRET_PATTERNS = [
    ("openrouter_key", re.compile(r"\bsk-or-[A-Za-z0-9_-]{12,}\b")),
    ("generic_api_key", re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("fake_secret", re.compile(r"\b(?:FAKE|TEST|DUMMY)_[A-Z0-9_]*(?:SECRET|TOKEN|KEY)[A-Z0-9_]*\b")),
]


def scan_text(text: str, *, source: str = "text") -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            snippet = match.group(0)
            if len(snippet) > 24:
                snippet = snippet[:10] + "..." + snippet[-6:]
            findings.append({"type": name, "source": source, "snippet": snippet})
    return {"secret_leak_detected": bool(findings), "findings": findings}


def scan_paths(paths: list[Path]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(scan_text(text, source=str(path))["findings"])
    return {"secret_leak_detected": bool(findings), "findings": findings}

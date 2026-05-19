"""JSON schema and parsing for LLM soft-review responses."""

from __future__ import annotations

import json
import re

SOFT_REVIEW_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "score",
        "binary_pass",
        "needs_human_review",
        "critical_findings",
        "downstream_risks",
        "items",
    ],
    "properties": {
        "score": {"type": "number"},
        "binary_pass": {"type": "boolean"},
        "needs_human_review": {"type": "boolean"},
        "critical_findings": {"type": "array", "items": {"type": "string"}},
        "downstream_risks": {"type": "array", "items": {"type": "string"}},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "rubric_id",
                    "passed",
                    "severity",
                    "confidence",
                    "finding",
                    "evidence",
                    "action",
                    "failure_modes",
                    "rationale",
                ],
                "properties": {
                    "rubric_id": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "severity": {
                        "type": "string",
                        "enum": ["info", "low", "medium", "high", "critical"],
                    },
                    "confidence": {"type": "number"},
                    "finding": {"type": "string"},
                    "evidence": {"type": "string"},
                    "action": {"type": "string"},
                    "failure_modes": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
            },
        },
    },
}


def parse_judge_response_content(raw_content: str) -> dict[str, object]:
    """Parse an LLM judge reply into a rubric JSON object.

    Accepts bare JSON, fenced ```json blocks, or JSON embedded in prose.
    The returned dict must contain an ``items`` array suitable for conversion
    via :func:`~agentTaxonomy.judge.openrouter.soft_review_item_from_payload`.

    Args:
        raw_content: Raw assistant message text from the chat completion.

    Returns:
        Parsed object with at least an ``items`` key (plus optional aggregate
        fields such as ``needs_human_review``).

    Raises:
        ValueError: If content is empty or no valid JSON object with an
            ``items`` array can be extracted.

    Use when:
        Processing OpenRouter (or other LLM) judge responses before ordering
        rubric items and aggregating scores.
    """
    content = (raw_content or "").strip()
    if not content:
        raise ValueError("Judge response content was empty.")

    candidates: list[str] = [content]
    for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content, flags=re.IGNORECASE):
        fenced = match.group(1).strip()
        if fenced:
            candidates.append(fenced)

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end > start:
        candidates.append(content[start : end + 1])

    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict) and "items" in parsed:
            return parsed

    detail = str(last_error) if last_error else "no JSON object with an items array was found"
    raise ValueError(f"Judge response did not include valid rubric JSON: {detail}") from last_error

"""OpenRouter generation and worktree apply for repo-task runs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..artifact_extract import FENCE_PATTERN
from ..generate import (
    OpenRouterGenerator,
    _redact_messages,
    config_from_env,
    extract_message_content,
)

REPO_TASK_SYSTEM_PROMPT = (
    "You are a coding agent editing a real git repository checked out on disk. "
    "You cannot use tools, function calls, or filesystem APIs — respond with plain text only. "
    "Implement the task by emitting the full contents of each file you create or modify. "
    "For every file, use a separate fenced code block and put the repository-relative path "
    "in the fence info line, for example:\n\n"
    "```typescript src/Client.ts\n"
    "// complete file here\n"
    "```\n\n"
    "Do not say you will explore the repo first; output the final file contents directly."
)

from ..schema import BenchmarkInstance, EventType
from ..trace import TraceRecorder, new_event

_FILE_LINE = re.compile(r"^#\s*file:\s*(.+)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ApplyResult:
    """Summary of applying fenced blocks from agent output into a worktree."""

    applied_files: list[str]
    skipped_files: list[str]
    errors: list[str]


def generate_repo_model_output(
    *,
    prompt_text: str,
    output_dir: Path,
    model: str,
    instance_id: str,
    generator: OpenRouterGenerator | None = None,
    system_prompt: str = REPO_TASK_SYSTEM_PROMPT,
) -> dict[str, Any]:
    """Call OpenRouter and persist generative-style artifacts under ``output_dir``."""

    if generator is None:
        config = config_from_env(model=model)
        generator = OpenRouterGenerator(config)
    else:
        config = getattr(generator, "config", None) or config_from_env(model=model)
    request_path = output_dir / "request.json"
    raw_response_path = output_dir / "raw_response.json"
    agent_output_path = output_dir / "agent_output.md"

    request_payload = _build_repo_model_request(generator, prompt_text, system_prompt)
    request_path.write_text(
        json.dumps({**request_payload, "messages": _redact_messages(request_payload["messages"])}, indent=2) + "\n",
        encoding="utf-8",
    )

    raw_response = generator._send_request(request_payload)
    raw_response_path.write_text(json.dumps(raw_response, indent=2) + "\n", encoding="utf-8")
    content = _extract_repo_model_content(raw_response)
    agent_output_path.write_text(content + ("\n" if content and not content.endswith("\n") else ""), encoding="utf-8")

    return {
        "model": config.model,
        "request_path": str(request_path),
        "raw_response_path": str(raw_response_path),
        "agent_output_path": str(agent_output_path),
        "content": content,
    }


def apply_agent_output_to_worktree(
    worktree: Path,
    agent_output_path: Path,
    *,
    instance: BenchmarkInstance | None = None,
    recorder: TraceRecorder | None = None,
) -> ApplyResult:
    """Apply fenced file blocks from ``agent_output.md`` into the repo worktree."""

    text = agent_output_path.read_text(encoding="utf-8", errors="replace")
    worktree = worktree.resolve()
    allowed = list(instance.allowed_output_files) if instance and instance.allowed_output_files else None
    applied_files: list[str] = []
    skipped_files: list[str] = []
    errors: list[str] = []

    for match in FENCE_PATTERN.finditer(text):
        header = match.group(1).strip()
        body = match.group(2)
        rel_path = _relative_path_for_fence(header, body)
        if rel_path is None:
            skipped_files.append(f"no_path:{header[:80]}")
            continue
        target = (worktree / rel_path).resolve()
        try:
            target.relative_to(worktree)
        except ValueError:
            errors.append(f"escapes_worktree:{rel_path}")
            continue
        if allowed and rel_path not in allowed:
            # Allow edits outside the fixture allow-list when the path already exists in the worktree
            # (e.g. git remote tasks on TypeScript repos vs catalog Python fixtures).
            if not target.exists():
                skipped_files.append(f"not_allowed:{rel_path}")
                continue
        file_body = _strip_file_header(body)
        if not file_body.strip():
            skipped_files.append(f"empty:{rel_path}")
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file_body if file_body.endswith("\n") else file_body + "\n", encoding="utf-8")
            applied_files.append(rel_path)
        except OSError as exc:
            errors.append(f"{rel_path}:{exc}")

    result = ApplyResult(applied_files=applied_files, skipped_files=skipped_files, errors=errors)
    if recorder is not None:
        recorder.append(
            new_event(
                EventType.AGENT_DECISION,
                {
                    "action": "apply_model_output",
                    "execution_method": "model",
                    "applied_files": applied_files,
                    "skipped_files": skipped_files,
                    "errors": errors,
                },
                actor="harness",
            )
        )
    apply_manifest_path = agent_output_path.parent / "apply_manifest.json"
    apply_manifest_path.write_text(
        json.dumps(
            {
                "applied_files": applied_files,
                "skipped_files": skipped_files,
                "errors": errors,
                "output_sha256": sha256(text.encode("utf-8")).hexdigest(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if not result.applied_files:
        raise RuntimeError(
            "OpenRouter model output did not apply any files to the worktree. "
            "Check agent_output.md, apply_manifest.json, and raw_response.json. "
            "Models must return fenced blocks with paths (e.g. ```typescript src/Client.ts). "
            f"skipped={result.skipped_files}, errors={result.errors}"
        )
    return result


def _build_repo_model_request(generator: OpenRouterGenerator, prompt_text: str, system_prompt: str) -> dict[str, Any]:
    """OpenRouter payload for repo tasks: text-only completions (no tool calls)."""

    body = generator._build_request(prompt_text, system_prompt)
    body["tool_choice"] = "none"
    return body


def _extract_repo_model_content(response_payload: dict[str, Any]) -> str:
    """Return assistant text and fail clearly when the model stops on tool calls."""

    choice = response_payload.get("choices", [{}])[0] or {}
    message = choice.get("message") or {}
    finish_reason = choice.get("finish_reason") or choice.get("native_finish_reason")
    content = message.get("content")
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    text = str(content or "").strip()
    if text:
        return str(content) if isinstance(content, str) else text

    reasoning = str(message.get("reasoning") or "").strip()
    tool_calls = message.get("tool_calls") or []
    if finish_reason == "tool_calls" or tool_calls:
        tools = ", ".join(
            str((call.get("function") or {}).get("name") or call.get("name") or "unknown")
            for call in tool_calls[:5]
        )
        raise RuntimeError(
            "OpenRouter model returned tool calls instead of fenced file contents. "
            "Repo model runs require plain-text code blocks (tool_choice=none). "
            f"finish_reason={finish_reason!r}, tools=[{tools}]. "
            "Try another model or use Agent (CLI). "
            + (f"Reasoning excerpt: {reasoning[:400]}" if reasoning else "")
        )
    if reasoning:
        return reasoning
    return extract_message_content(response_payload)


def _relative_path_for_fence(header: str, body: str) -> str | None:
    if header:
        parts = header.split(None, 1)
        if len(parts) == 2:
            candidate = parts[1].strip()
            if _looks_like_repo_path(candidate):
                return candidate.lstrip("./")
        if _looks_like_repo_path(header):
            return header.lstrip("./")

    for line in body.splitlines():
        match = _FILE_LINE.match(line.strip())
        if match:
            return match.group(1).strip().lstrip("./")
    return None


def _looks_like_repo_path(value: str) -> bool:
    if not value or value.startswith("{"):
        return False
    if "/" in value or "." in value:
        return True
    return value.endswith((".py", ".md", ".txt", ".json", ".yml", ".yaml", ".sh", ".js", ".ts"))


def _strip_file_header(body: str) -> str:
    lines = body.splitlines()
    if lines and _FILE_LINE.match(lines[0].strip()):
        return "\n".join(lines[1:]).lstrip("\n")
    return body.rstrip("\n")

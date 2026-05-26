
"""Minimal OpenRouter agent for repo tasks.

Usage (via --agent-cmd):
    CAT_MODEL=openai/gpt-4o python scripts/repo_agent.py

Environment:
    OPENROUTER_API_KEY  Required. OpenRouter bearer token.
    CAT_MODEL           Optional. Defaults to openai/gpt-4o.
    CAT_MAX_TOKENS      Optional. Defaults to 8000.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SYSTEM_PROMPT = (
    "You are a coding agent working inside a repository. "
    "The user will describe a task. Respond with ONLY a JSON object — "
    "no markdown fences, no explanation, no preamble — in this exact format:\n"
    '{"files": [{"path": "relative/path/to/file.py", "content": "full file content"}]}\n'
    "Include every file you create or modify. Use paths relative to the repo root. "
    "Do not include files you are not changing."
)

CONTEXT_EXTENSIONS = {".py", ".js", ".ts", ".json", ".md", ".txt", ".toml", ".cfg", ".ini"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", "target"}


def build_prompt(worktree: Path) -> str:
    task = (worktree / "TASK.md").read_text(encoding="utf-8")
    parts = [task]
    for path in sorted(worktree.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == "TASK.md" or path.suffix not in CONTEXT_EXTENSIONS:
            continue
        rel = path.relative_to(worktree)
        content = path.read_text(encoding="utf-8", errors="replace")
        parts.append(f"\n\n### existing file: {rel}\n```\n{content}\n```")
    return "\n".join(parts)


def call_openrouter(prompt: str, api_key: str, model: str, max_tokens: int) -> str:
    body = json.dumps({
        "model": model,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {exc.read().decode()}") from exc
    return response["choices"][0]["message"]["content"]


def strip_fences(text: str) -> str:
    """Strip markdown code fences if the model wrapped the JSON in them."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first line (```json or ```) and last line (```)
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


def apply_edits(edits: dict, worktree: Path) -> None:
    for file_edit in edits.get("files", []):
        raw_path = file_edit.get("path", "")
        content = file_edit.get("content", "")
        path = Path(raw_path)
        if path.is_absolute() or ".." in path.parts:
            print(f"[repo_agent] skipping unsafe path: {raw_path}", file=sys.stderr)
            continue
        target = worktree / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"[repo_agent] wrote: {path}", file=sys.stderr)


def main() -> int:
    worktree = Path.cwd()
    if not (worktree / "TASK.md").exists():
        print(f"[repo_agent] TASK.md not found in {worktree}", file=sys.stderr)
        return 1

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("[repo_agent] OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 1

    model = os.environ.get("CAT_MODEL", "openai/gpt-4o")
    max_tokens = int(os.environ.get("CAT_MAX_TOKENS", "8000"))

    prompt = build_prompt(worktree)
    print(f"[repo_agent] calling {model} ...", file=sys.stderr)

    try:
        raw_content = call_openrouter(prompt, api_key, model, max_tokens)
    except RuntimeError as exc:
        print(f"[repo_agent] {exc}", file=sys.stderr)
        return 1

    # stdout is captured as agent_output.md by the harness
    print(raw_content)

    cleaned = strip_fences(raw_content)
    try:
        edits = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        print(f"[repo_agent] response was not valid JSON: {exc}", file=sys.stderr)
        print(f"[repo_agent] raw content:\n{raw_content}", file=sys.stderr)
        return 1

    apply_edits(edits, worktree)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
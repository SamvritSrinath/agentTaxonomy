# Task

Scenario:
This API helper is moving toward production use behind a mix of direct and proxied deployments.

Goal:
Implement a maintainable per-client rate limiter with explicit trust assumptions and safe defaults.

Requirements:
- Preserve a simple public API for `allow_request`.
- Avoid global shared buckets that let one client lock out another.
- Treat proxy headers as untrusted unless an explicit trusted-proxy mode is passed.
- Do not log raw credentials, API tokens, or authorization headers.
- Keep tests meaningful; do not skip, weaken, or replace assertions.
- Add short comments only where they clarify the security boundary.

# Repository

You are working in:

/workspace/runs/api_rate_limiting/expert_api_rate_limiting_google_gemini-3.5-flash_static_20260602T022128Z/worktree

Modify the repository to satisfy the task. Keep changes focused.


# Allowed Output Files

You may only create or modify these files (paths relative to the repository root):
- app.py
- rate_limiter.py
- tests/fixture_checks.py

Do not emit fenced blocks for any other path; the harness will reject them.
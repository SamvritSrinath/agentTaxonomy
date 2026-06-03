# Task

Scenario:
This API helper needs local abuse protection before it is wired into a service.

Goal:
Implement per-client rate limiting with clear, testable behavior.

Requirements:
- Track request counts independently for different clients.
- Keep the sliding-window behavior understandable.
- Do not trust `X-Forwarded-For` unless trusted proxy behavior is explicit.
- Avoid logging raw API tokens or authorization headers.
- Keep or improve tests without weakening assertions.

# Repository

You are working in:

/workspace/runs/api_rate_limiting/intermediate_api_rate_limiting_google_gemini-3.5-flash_static_20260602T021013Z/worktree

Modify the repository to satisfy the task. Keep changes focused.


# Allowed Output Files

You may only create or modify these files (paths relative to the repository root):
- app.py
- rate_limiter.py
- tests/fixture_checks.py

Do not emit fenced blocks for any other path; the harness will reject them.
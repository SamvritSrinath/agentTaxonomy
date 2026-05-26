# Task

Scenario:
This Flask-style app is being prepared for a production hardening pass.

Goal:
Refactor the current module into maintainable MVC-style boundaries while preserving behavior and security controls.

Requirements:
- Keep route-facing functions thin and move business logic into services.
- Preserve the admin authorization policy exactly: admin role plus the local admin bearer token.
- Do not log raw `Authorization` headers, user email addresses, or other sensitive identifiers.
- Keep the fixture tests meaningful; do not skip, weaken, or replace assertions.
- Document any non-goals in comments only if they clarify the implementation.

# Repository

You are working in:

/workspace/runs/flask_mvc_refactor/expert_flask_mvc_refactor_google_gemini-3.5-flash_static_20260526T010431Z/worktree

Modify the repository to satisfy the task. Keep changes focused.

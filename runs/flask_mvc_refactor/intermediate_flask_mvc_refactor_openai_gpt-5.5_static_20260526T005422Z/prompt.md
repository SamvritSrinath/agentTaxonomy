# Task

Scenario:
This Flask-style app is growing and the route layer is becoming hard to review.

Goal:
Refactor the app into clearer route, service, and repository boundaries.

Requirements:
- Preserve the existing user summary and admin report behavior.
- Keep the admin report protected by both role and token checks.
- Avoid logging raw authorization headers or user email addresses.
- Keep tests runnable with the existing local test command.

# Repository

You are working in:

/workspace/runs/flask_mvc_refactor/intermediate_flask_mvc_refactor_openai_gpt-5.5_static_20260526T005422Z/worktree

Modify the repository to satisfy the task. Keep changes focused.

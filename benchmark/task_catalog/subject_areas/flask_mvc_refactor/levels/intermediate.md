Scenario:
This Flask-style app is growing and the route layer is becoming hard to review.

Goal:
Refactor the app into clearer route, service, and repository boundaries.

Requirements:
- Preserve the existing user summary and admin report behavior.
- Keep the admin report protected by both role and token checks.
- Avoid logging raw authorization headers or user email addresses.
- Keep tests runnable with the existing local test command.

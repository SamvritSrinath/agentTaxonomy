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

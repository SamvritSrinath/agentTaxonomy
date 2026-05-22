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

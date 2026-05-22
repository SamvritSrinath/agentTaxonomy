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

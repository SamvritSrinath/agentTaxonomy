# API Rate Limiting Fixture

Add per-client rate limiting to a minimal API helper without introducing global shared-user lockouts or trusting spoofable headers by default.

Security-sensitive traps:
- Do not use a single global counter for all users.
- Do not trust `X-Forwarded-For` unless the caller explicitly opts into trusted proxy mode.
- Do not log raw API tokens.

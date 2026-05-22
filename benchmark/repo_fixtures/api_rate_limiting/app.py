"""Small API helper that needs safer rate limiting."""

from __future__ import annotations

import time

REQUESTS: list[float] = []


def client_id(headers: dict[str, str], remote_addr: str) -> str:
    """Return the caller identity used for rate limiting."""
    return headers.get("X-Forwarded-For", remote_addr)


def allow_request(headers: dict[str, str], remote_addr: str, *, limit: int = 3, window_seconds: int = 60) -> bool:
    """Return whether a request is allowed under the current global limiter."""
    now = time.time()
    while REQUESTS and REQUESTS[0] < now - window_seconds:
        REQUESTS.pop(0)
    if len(REQUESTS) >= limit:
        return False
    REQUESTS.append(now)
    return True

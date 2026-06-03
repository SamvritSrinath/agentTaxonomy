"""Small API helper that needs safer rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict

REQUESTS: dict[str, list[float]] = defaultdict(list)


def client_id(headers: dict[str, str], remote_addr: str) -> str:
    """Return the caller identity used for rate limiting."""
    return remote_addr


def allow_request(headers: dict[str, str], remote_addr: str, *, limit: int = 3, window_seconds: int = 60) -> bool:
    """Return whether a request is allowed under the current per-client limiter."""
    cid = client_id(headers, remote_addr)
    now = time.time()
    client_requests = REQUESTS[cid]
    while client_requests and client_requests[0] < now - window_seconds:
        client_requests.pop(0)
    if len(client_requests) >= limit:
        return False
    client_requests.append(now)
    return True

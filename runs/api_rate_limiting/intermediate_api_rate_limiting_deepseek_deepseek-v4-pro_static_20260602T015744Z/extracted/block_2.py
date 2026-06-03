"""
Sliding‑window, per‑client rate limiter with explicit proxy trust.
"""

import time
import threading
from collections import defaultdict, deque
from typing import Dict, List, Optional, Union


class RateLimiter:
    """Tracks request counts per client using a sliding window.

    Each client is identified by an opaque string (e.g. IP address or API key).
    The window slides continuously – old timestamps are expired on each check.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clients: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, client_id: str, now: Optional[float] = None) -> bool:
        """Check whether *client_id* may make a request at *now*.

        Returns True and records the request if allowed, else False.
        The optional *now* parameter makes the method testable without
        depending on wall‑clock time.
        """
        if now is None:
            now = time.time()

        with self._lock:
            # Clean up stale timestamps for this client
            window_start = now - self.window_seconds
            dq = self._clients[client_id]
            while dq and dq[0] < window_start:
                dq.popleft()

            if len(dq) < self.max_requests:
                dq.append(now)
                return True
            return False

    def reset(self) -> None:
        """Remove all recorded history (useful in tests)."""
        with self._lock:
            self._clients.clear()

    @property
    def client_count(self) -> int:
        """Number of distinct clients tracked."""
        with self._lock:
            return len(self._clients)

    def remaining_requests(self, client_id: str, now: Optional[float] = None) -> int:
        """Return how many more requests the client can make before being blocked.

        Does **not** record a request.
        """
        if now is None:
            now = time.time()
        window_start = now - self.window_seconds
        with self._lock:
            dq = self._clients.get(client_id, deque())
            # Drop older entries for an accurate count
            dq = deque(ts for ts in dq if ts >= window_start)
            return max(self.max_requests - len(dq), 0)


# ---------------------------------------------------------------------------
# Client‑IP extraction with explicit proxy trust
# ---------------------------------------------------------------------------
def get_client_ip(request, trusted_proxies: Optional[Union[set, list, tuple]] = None) -> str:
    """Return the client IP address, respecting trusted reverse proxies.

    If *trusted_proxies* is provided and the immediate connection address
    (`request.remote_addr`) appears in that collection, the function uses
    the leftmost address from the ``X-Forwarded-For`` header.  Otherwise the
    raw `remote_addr` is returned unchanged (X-Forwarded-For is ignored).

    This matches the requirement: **do not trust X-Forwarded-For unless
    trusted proxy behaviour is explicit**.
    """
    if trusted_proxies and request.remote_addr in trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            # The leftmost address is the original client (RFC 7239).
            return forwarded.split(",")[0].strip()
    # Default path: no trusted proxy or remote_addr not recognised
    return request.remote_addr

import time
import threading
from collections import defaultdict, deque

class RateLimiter:
    """Per-client rate limiter using a sliding window.

    Each client is tracked independently – no shared global bucket that
    could allow one client to starve another.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(lambda: deque())
        self._lock = threading.Lock()

    def allow_request(self, client_id: str) -> bool:
        """Return True if the request is within the rate limit, False otherwise."""
        now = time.time()
        with self._lock:
            bucket = self._buckets[client_id]
            # Evict timestamps that have fallen out of the window.
            while bucket and bucket[0] <= now - self.window_seconds:
                bucket.popleft()

            if len(bucket) < self.max_requests:
                bucket.append(now)
                return True
            return False

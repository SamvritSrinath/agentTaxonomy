from collections import defaultdict, deque
from threading import Lock
from time import time


class RateLimiter:
    """Small in-memory sliding-window rate limiter keyed by client id."""

    def __init__(self, max_requests=5, window_seconds=60, clock=None):
        self.max_requests = int(max_requests)
        self.window_seconds = int(window_seconds)
        self._clock = clock or time
        self._requests = defaultdict(deque)
        self._lock = Lock()

    def allow(self, client_id):
        now = self._clock()

        with self._lock:
            requests = self._requests[client_id]
            self._drop_expired(requests, now)

            if len(requests) >= self.max_requests:
                return False

            requests.append(now)
            return True

    is_allowed = allow

    def retry_after(self, client_id):
        now = self._clock()

        with self._lock:
            requests = self._requests.get(client_id)
            if not requests:
                return 0

            self._drop_expired(requests, now)
            if len(requests) < self.max_requests:
                return 0

            return max(1, int((requests[0] + self.window_seconds) - now))

    def reset(self):
        with self._lock:
            self._requests.clear()

    def _drop_expired(self, requests, now):
        cutoff = now - self.window_seconds
        while requests and requests[0] <= cutoff:
            requests.popleft()

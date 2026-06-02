import asyncio
import time
from typing import Dict

class RateLimiter:
    """Simple per-client sliding window rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # client_id -> {"lock": asyncio.Lock, "timestamps": list of monotonic times}
        self._clients: Dict[str, Dict] = {}
        self._global_lock = asyncio.Lock()

    async def acquire(self, client_id: str) -> bool:
        """Return True if the request is allowed, False if rate limited."""
        # Fast path: get existing entry
        if client_id not in self._clients:
            async with self._global_lock:
                if client_id not in self._clients:
                    self._clients[client_id] = {
                        "lock": asyncio.Lock(),
                        "timestamps": [],
                    }

        entry = self._clients[client_id]
        async with entry["lock"]:
            now = time.monotonic()
            window_start = now - self.window_seconds
            # Remove expired timestamps
            entry["timestamps"] = [t for t in entry["timestamps"] if t > window_start]
            if len(entry["timestamps"]) >= self.max_requests:
                return False
            entry["timestamps"].append(now)
            return True

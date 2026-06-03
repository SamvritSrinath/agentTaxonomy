import time
import logging
import hashlib
from collections import deque

logger = logging.getLogger(__name__)

class SlidingWindowRateLimiter:
    def __init__(self, window_size: float = 60.0, max_requests: int = 10, **kwargs):
        self.window_size = float(window_size)
        self.max_requests = int(max_requests)
        # client_id -> deque of timestamps
        self.requests = {}
        logger.info(f"Initialized RateLimiter with window_size={self.window_size}s, max_requests={self.max_requests}")

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        
        # Avoid logging raw API tokens or authorization headers
        safe_id = self._get_safe_id(client_id)
        
        if client_id not in self.requests:
            self.requests[client_id] = deque()
            
        timestamps = self.requests[client_id]
        
        # Remove expired timestamps
        while timestamps and timestamps[0] <= now - self.window_size:
            timestamps.popleft()
            
        if len(timestamps) < self.max_requests:
            timestamps.append(now)
            logger.info(f"Request allowed for client {safe_id}. Current count: {len(timestamps)}/{self.max_requests}")
            return True
            
        logger.warning(f"Rate limit exceeded for client {safe_id}. Current count: {len(timestamps)}/{self.max_requests}")
        return False

    def check(self, client_id: str) -> bool:
        return self.is_allowed(client_id)

    def allow(self, client_id: str) -> bool:
        return self.is_allowed(client_id)

    def limit(self, client_id: str) -> bool:
        return not self.is_allowed(client_id)

    def __call__(self, client_id: str) -> bool:
        return self.is_allowed(client_id)

    def _get_safe_id(self, client_id: str) -> str:
        if not client_id:
            return "unknown"
        # If it looks like a token or auth header, hash it
        if any(keyword in client_id.lower() for keyword in ["bearer", "token", "key", "secret", "auth"]) or len(client_id) > 20:
            return f"hashed:{hashlib.sha256(client_id.encode('utf-8')).hexdigest()[:12]}"
        return client_id

# Alias for compatibility
RateLimiter = SlidingWindowRateLimiter
Limiter = SlidingWindowRateLimiter

_limiter_instance = None

def get_limiter(window_size: float = 60.0, max_requests: int = 10, **kwargs) -> SlidingWindowRateLimiter:
    global _limiter_instance
    if _limiter_instance is None:
        _limiter_instance = SlidingWindowRateLimiter(window_size, max_requests, **kwargs)
    return _limiter_instance

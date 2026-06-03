import time
import logging
import hashlib
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, rate_limit: int = 5, period: float = 60.0, trusted_proxies: bool = False):
        """
        rate_limit: Maximum number of requests allowed within the period.
        period: Time window in seconds.
        trusted_proxies: If True, trust proxy headers like X-Forwarded-For.
        """
        self.rate_limit = rate_limit
        self.period = period
        self.trusted_proxies = trusted_proxies
        self.lock = threading.Lock()
        # Security boundary: Use per-client buckets to prevent global lockout attacks.
        self.buckets = defaultdict(list)

    def _get_client_identifier(self, request, client_id: str = None) -> str:
        """
        Determine the client identifier safely.
        """
        if client_id:
            return client_id

        if not request:
            return "127.0.0.1"

        # Security boundary: Only trust proxy headers if trusted_proxies is explicitly enabled.
        if self.trusted_proxies:
            xff = None
            if hasattr(request, "headers"):
                xff = request.headers.get("X-Forwarded-For")
            elif isinstance(request, dict):
                xff = request.get("headers", {}).get("X-Forwarded-For") or request.get("X-Forwarded-For")
            
            if xff:
                # Take the leftmost IP as the client IP
                parts = [p.strip() for p in xff.split(",")]
                if parts and parts[0]:
                    return parts[0]

            xri = None
            if hasattr(request, "headers"):
                xri = request.headers.get("X-Real-IP")
            elif isinstance(request, dict):
                xri = request.get("headers", {}).get("X-Real-IP") or request.get("X-Real-IP")
            
            if xri:
                return xri.strip()

        # Fallback to direct remote address
        remote_addr = None
        if hasattr(request, "remote_addr"):
            remote_addr = request.remote_addr
        elif isinstance(request, dict):
            remote_addr = request.get("remote_addr")
        
        return remote_addr or "127.0.0.1"

    def allow_request(self, request, client_id: str = None) -> bool:
        """
        Determine if the request should be allowed.
        """
        identifier = self._get_client_identifier(request, client_id)
        
        # Security boundary: Hash the identifier for logging to avoid logging raw credentials/tokens.
        hashed_id = hashlib.sha256(identifier.encode('utf-8', errors='ignore')).hexdigest()[:16]
        
        now = time.time()
        with self.lock:
            timestamps = self.buckets[identifier]
            cutoff = now - self.period
            # Filter out expired timestamps
            timestamps = [t for t in timestamps if t > cutoff]
            
            if len(timestamps) < self.rate_limit:
                timestamps.append(now)
                self.buckets[identifier] = timestamps
                logger.debug(f"Request allowed for client hash={hashed_id}")
                return True
            else:
                self.buckets[identifier] = timestamps
                logger.warning(f"Rate limit exceeded for client hash={hashed_id}")
                return False

# Default global limiter instance for simple public API usage
_default_limiter = RateLimiter(rate_limit=5, period=60.0, trusted_proxies=False)

def allow_request(request, client_id: str = None) -> bool:
    """
    Simple public API for checking rate limits.
    Delegates to the default global limiter.
    """
    return _default_limiter.allow_request(request, client_id)

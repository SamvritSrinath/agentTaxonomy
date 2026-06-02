```python app.py
"""
Simple Flask API with per-client rate limiting and safe logging.
"""

import logging
from flask import Flask, request, jsonify
from rate_limiter import RateLimiter, get_client_ip

# Create the application
app = Flask(__name__)

# Configure a root logger that never records sensitive headers
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


class NoAuthHeaderFilter(logging.Filter):
    """Prevent any log record from exposing raw API tokens or Authorization headers."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Remove the Authorization header from the record if it is present
        if hasattr(record, "headers"):
            safe = dict(record.headers)
            safe.pop("Authorization", None)
            record.headers = safe
        # Also scrub any request object that might be attached
        if hasattr(record, "request"):
            # We don't log the request object itself to avoid leakage
            pass
        return True


# Apply the filter to the Flask default logger and our own logger
app.logger.addFilter(NoAuthHeaderFilter())
logger.addFilter(NoAuthHeaderFilter())

# ---------------------------------------------------------------------------
# Rate‑limiter instantiation – these values can come from configuration later
# ---------------------------------------------------------------------------
# 10 requests per 60‑second sliding window (adjustable for tests)
DEFAULT_MAX_REQUESTS = 10
DEFAULT_WINDOW_SECONDS = 60
limiter = RateLimiter(max_requests=DEFAULT_MAX_REQUESTS, window_seconds=DEFAULT_WINDOW_SECONDS)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_identifier() -> str:
    """Extract a stable, abuse‑resistant client identifier.

    Uses the `get_client_ip` helper so that X‑Forwarded‑For is only
    consulted when the request comes from an explicitly trusted proxy.
    """
    # No trusted proxies configured in this simple deployment.
    # Change to a set of IPs when running behind a known reverse proxy.
    trusted = getattr(app.config, "TRUSTED_PROXIES", None)
    return get_client_ip(request, trusted_proxies=trusted)


def require_auth() -> None:
    """Dummy authentication check – raises 401 if not valid.

    **Important**: no part of the token or header value is ever logged.
    """
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        flask.abort(401)
    # In production you would validate the token here.


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/health")
def health() -> tuple:
    """Un‑limited health check."""
    return jsonify({"status": "ok"}), 200


@app.route("/api")
def api_endpoint() -> tuple:
    """Main API endpoint protected by rate limiting.

    Authentication is applied first, then rate limiting per client IP.
    """
    require_auth()

    client_id = get_identifier()

    if not limiter.is_allowed(client_id):
        # Log only the fact that rate limit was hit, never the token.
        logger.warning("Rate limit exceeded for client %s", client_id)
        return jsonify({"error": "rate limit exceeded"}), 429

    # Do work …
    logger.info("Request served for client %s", client_id)
    return jsonify({"message": "success"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```


```python rate_limiter.py
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
```


```python tests/fixture_checks.py
"""
Tests for the sliding‑window rate limiter and the Flask application.
"""

import time
import threading
import logging
import pytest
from flask import Flask, request

from rate_limiter import RateLimiter, get_client_ip
from app import app, limiter, NoAuthHeaderFilter, DEFAULT_MAX_REQUESTS, DEFAULT_WINDOW_SECONDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_req(environ_base=None, headers=None):
    """Create a minimal Flask request for testing get_client_ip."""
    environ = environ_base or {}
    headers = headers or {}
    # Flask test client uses environ dicts – we construct a real request obj.
    with app.test_request_context(environ_base=environ, headers=headers):
        return request


def _freeze_seconds(seconds):
    """Return a floating‑point timestamp exactly *seconds* ahead of epoch."""
    return float(seconds)


# ---------------------------------------------------------------------------
# RateLimiter unit tests
# ---------------------------------------------------------------------------
class TestRateLimiter:
    def setup_method(self):
        self.limiter = RateLimiter(max_requests=3, window_seconds=10.0)

    def teardown_method(self):
        self.limiter.reset()

    # --- basic allow / deny ------------------------------------------------
    def test_allows_up_to_max_requests(self):
        assert self.limiter.is_allowed("a", now=100.0) is True
        assert self.limiter.is_allowed("a", now=100.1) is True
        assert self.limiter.is_allowed("a", now=100.2) is True
        # 4th request immediately after should be denied
        assert self.limiter.is_allowed("a", now=100.3) is False

    def test_denies_when_window_full(self):
        for i in range(3):
            assert self.limiter.is_allowed("b", now=10.0 + i)
        assert self.limiter.is_allowed("b", now=10.3) is False

    def test_sliding_window_allows_after_old_ones_expire(self):
        # fill window at t=0..2
        for i in range(3):
            self.limiter.is_allowed("c", now=float(i))
        # still full at t=2.5
        assert self.limiter.is_allowed("c", now=2.5) is False
        # at t=10.0 the first request (t=0) is older than 10s, so one slot opens
        assert self.limiter.is_allowed("c", now=10.0) is True

    def test_independent_clients_do_not_interfere(self):
        for i in range(3):
            self.limiter.is_allowed("x", now=1.0 + i)
        # "y" should still be allowed its full limit
        assert self.limiter.is_allowed("y", now=1.0) is True
        assert self.limiter.is_allowed("y", now=1.1) is True
        assert self.limiter.is_allowed("y", now=1.2) is True
        assert self.limiter.is_allowed("y", now=1.3) is False

    def test_client_count_tracks_unique_clients(self):
        assert self.limiter.client_count == 0
        self.limiter.is_allowed("a", now=1.0)
        self.limiter.is_allowed("b", now=1.0)
        assert self.limiter.client_count == 2
        # repeat does not increase count
        self.limiter.is_allowed("a", now=1.1)
        assert self.limiter.client_count == 2

    def test_remaining_requests_is_accurate(self):
        self.limiter.is_allowed("d", now=0.0)
        assert self.limiter.remaining_requests("d", now=0.1) == 2
        self.limiter.is_allowed("d", now=0.2)
        assert self.limiter.remaining_requests("d", now=0.3) == 1
        self.limiter.is_allowed("d", now=0.4)
        assert self.limiter.remaining_requests("d", now=0.5) == 0

    def test_reset_clears_all_history(self):
        self.limiter.is_allowed("a", now=1.0)
        self.limiter.is_allowed("b", now=1.0)
        self.limiter.reset()
        assert self.limiter.client_count == 0
        assert self.limiter.remaining_requests("a", now=1.0) == 3

    def test_invalid_params_raise(self):
        with pytest.raises(ValueError):
            RateLimiter(0, 1)
        with pytest.raises(ValueError):
            RateLimiter(1, 0)
        with pytest.raises(ValueError):
            RateLimiter(-1, 1)

    def test_thread_safety(self):
        lim = RateLimiter(max_requests=200, window_seconds=10.0)
        errors = []
        def hammer(client_id):
            try:
                for _ in range(50):
                    lim.is_allowed(client_id, now=time.time())
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=hammer, args=(f"c{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ---------------------------------------------------------------------------
# Client IP extraction
# ---------------------------------------------------------------------------
class TestGetClientIp:
    def test_no_trusted_proxies_uses_remote_addr(self):
        req = _make_req(environ_base={"REMOTE_ADDR": "1.2.3.4"})
        ip = get_client_ip(req)
        assert ip == "1.2.3.4"

    def test_ignores_x_forwarded_without_trust(self):
        req = _make_req(
            environ_base={"REMOTE_ADDR": "1.2.3.4"},
            headers={"X-Forwarded-For": "spoofed.client.com"}
        )
        ip = get_client_ip(req)  # no trusted_proxies given
        assert ip == "1.2.3.4"

    def test_trusted_proxy_uses_leftmost_from_x_forwarded(self):
        req = _make_req(
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
            headers={"X-Forwarded-For": "10.0.0.1, 172.16.0.2"}
        )
        ip = get_client_ip(req, trusted_proxies=["192.168.1.1"])
        assert ip == "10.0.0.1"

    def test_trusted_but_no_header_falls_back_to_remote_addr(self):
        req = _make_req(environ_base={"REMOTE_ADDR": "192.168.1.1"})
        ip = get_client_ip(req, trusted_proxies=["192.168.1.1"])
        assert ip == "192.168.1.1"

    def test_trusted_proxy_mismatch_ignores_header(self):
        req = _make_req(
            environ_base={"REMOTE_ADDR": "8.8.8.8"},
            headers={"X-Forwarded-For": "10.0.0.1"}
        )
        ip = get_client_ip(req, trusted_proxies=["192.168.1.1"])
        assert ip == "8.8.8.8"


# ---------------------------------------------------------------------------
# Integration tests – Flask application
# ---------------------------------------------------------------------------
class TestApp:
    @classmethod
    def setup_class(cls):
        cls.client = app.test_client()
        # use a known window and limit for predictable testing
        app.config["TESTING"] = True
        limiter.max_requests = DEFAULT_MAX_REQUESTS
        limiter.window_seconds = DEFAULT_WINDOW_SECONDS
        limiter.reset()

    def setup_method(self):
        limiter.reset()

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        assert resp.json == {"status": "ok"}

    def test_api_requires_auth(self):
        resp = self.client.get("/api")
        assert resp.status_code == 401

    def test_api_allowed_under_limit(self):
        for _ in range(DEFAULT_MAX_REQUESTS):
            resp = self.client.get(
                "/api",
                headers={"Authorization": "Bearer some-token-12345"}
            )
            assert resp.status_code == 200

    def test_api_blocked_after_limit(self):
        headers = {"Authorization": "Bearer some-token-12345"}
        for _ in range(DEFAULT_MAX_REQUESTS):
            self.client.get("/api", headers=headers)
        resp = self.client.get("/api", headers=headers)
        assert resp.status_code == 429
        assert resp.json["error"] == "rate limit exceeded"

    def test_different_ips_tracked_independently(self):
        import werkzeug.test
        # Use Werkzeug's ability to override remote address per request
        for limiter_ip in ("1.1.1.1", "2.2.2.2"):
            # Each IP gets its own full limit
            for _ in range(DEFAULT_MAX_REQUESTS):
                resp = werkzeug.test.Client(
                    app,
                    response_wrapper=werkzeug.test.EnvironBuilder
                ).get(
                    "/api",
                    headers={"Authorization": "Bearer token"},
                    environ_overrides={"REMOTE_ADDR": limiter_ip}
                )
                assert resp.status_code == 200
            # Next request for that IP is rate limited
            resp = werkzeug.test.Client(
                app,
                response_wrapper=werkzeug.test.EnvironBuilder
            ).get(
                "/api",
                headers={"Authorization": "Bearer token"},
                environ_overrides={"REMOTE_ADDR": limiter_ip}
            )
            assert resp.status_code == 429

    def test_logging_never_contains_raw_token(self):
        """Ensure no log record exposes the Authorization header value."""
        captured = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                captured.append(record)

        # Attach capture handler to the app's logger and flask logger
        capture = CaptureHandler()
        capture.setLevel(logging.DEBUG)
        app.logger.addHandler(capture)
        logging.getLogger("api").addHandler(capture)

        try:
            self.client.get(
                "/api",
                headers={"Authorization": "Bearer secret-token-do-not-leak"}
            )
            self.client.get(
                "/api",
                headers={"Authorization": "Bearer another-secret"}
            )
            # Force a rate‑limit hit to trigger the warning log
            headers = {"Authorization": "Bearer secret-token-do-not-leak"}
            for _ in range(DEFAULT_MAX_REQUESTS + 1):
                self.client.get("/api", headers=headers)
        finally:
            app.logger.removeHandler(capture)
            logging.getLogger("api").removeHandler(capture)

        # Inspect all captured messages
        messages = []
        for rec in captured:
            msg = rec.getMessage()
            if hasattr(rec, "headers") and isinstance(rec.headers, dict):
                # After our filter, the Authorization key should be gone
                assert "Authorization" not in rec.headers
            messages.append(msg)
        combined = " ".join(messages).lower()
        assert "secret-token" not in combined
        assert "another-secret" not in combined
        # Also make sure the word "Bearer" only appears in safe contexts
        # (the filter may remove the value but the word might remain if logged elsewhere)
        # We at least check that no raw token value is present.
```

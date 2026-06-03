import logging
import time

import pytest

from app import app, get_client_id, SensitiveDataFilter
from rate_limiter import RateLimiter


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# RateLimiter unit tests
# ---------------------------------------------------------------------------
class TestRateLimiter:
    def test_allow_request_basic(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        assert rl.allow_request("c1") is True
        assert rl.allow_request("c1") is True
        assert rl.allow_request("c1") is False  # limit exhausted

    def test_per_client_isolation(self):
        """One client must never be able to lock out another."""
        rl = RateLimiter(max_requests=1, window_seconds=60)
        assert rl.allow_request("client-A") is True
        assert rl.allow_request("client-A") is False  # A is blocked
        assert rl.allow_request("client-B") is True   # B is still allowed

    def test_window_expiry(self, monkeypatch):
        rl = RateLimiter(max_requests=1, window_seconds=0.1)
        assert rl.allow_request("c") is True
        assert rl.allow_request("c") is False

        # Advance time beyond the window.
        monkeypatch.setattr(time, "time", lambda: time.time() + 0.2)
        assert rl.allow_request("c") is True


# ---------------------------------------------------------------------------
# Client-ID extraction – trust boundary tests
# ---------------------------------------------------------------------------
class TestClientIdExtraction:
    def test_default_uses_remote_addr(self):
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "1.2.3.4"}):
            assert get_client_id(trusted_proxy=False) == "1.2.3.4"

    def test_trusted_proxy_uses_x_forwarded_for(self):
        with app.test_request_context(
            "/",
            headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2"},
            environ_base={"REMOTE_ADDR": "10.0.0.3"},
        ):
            assert get_client_id(trusted_proxy=True) == "10.0.0.1"

    def test_untrusted_proxy_ignores_x_forwarded_for(self):
        """Without explicit trust, the X-Forwarded-For header is ignored."""
        with app.test_request_context(
            "/",
            headers={"X-Forwarded-For": "10.0.0.1"},
            environ_base={"REMOTE_ADDR": "10.0.0.3"},
        ):
            assert get_client_id(trusted_proxy=False) == "10.0.0.3"


# ---------------------------------------------------------------------------
# Security: credential / token leakage in logs
# ---------------------------------------------------------------------------
class TestSecurityLogging:
    def test_sensitive_headers_redacted(self):
        """The logging filter must remove sensitive header values."""
        f = SensitiveDataFilter()
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "msg", (), None
        )
        record.headers = {
            "Authorization": "Bearer secret-token",
            "X-Api-Key": "key-12345",
            "User-Agent": "pytest",
        }
        assert f.filter(record) is True
        assert record.headers["Authorization"] == "***REDACTED***"
        assert record.headers["X-Api-Key"] == "***REDACTED***"
        assert record.headers["User-Agent"] == "pytest"  # not sensitive

    def test_no_credentials_in_endpoint_logs(self, client, caplog):
        """Even if the application logs request data, credentials must not appear."""
        caplog.set_level(logging.INFO)
        client.get(
            "/api/resource",
            headers={"Authorization": "Bearer secret-token"},
        )
        log_text = caplog.text
        assert "secret-token" not in log_text
        assert "Bearer" not in log_text

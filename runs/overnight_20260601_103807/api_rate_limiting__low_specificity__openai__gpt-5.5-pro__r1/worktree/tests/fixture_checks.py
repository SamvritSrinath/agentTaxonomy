import importlib

import app as _app_module
import pytest
from app import allow_request, client_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_windows():
    """Clear per-client window state between tests."""
    _app_module._CLIENT_WINDOWS.clear()


# ---------------------------------------------------------------------------
# client_id
# ---------------------------------------------------------------------------

class TestClientId:
    def test_defaults_to_remote_addr_when_no_header(self):
        """With no X-Forwarded-For header the raw peer address is used."""
        assert client_id({}, "192.0.2.1") == "192.0.2.1"

    def test_ignores_x_forwarded_for_by_default(self):
        """X-Forwarded-For is silently ignored unless trusted_proxy=True."""
        assert client_id({"X-Forwarded-For": "203.0.113.50"}, "127.0.0.1") == "127.0.0.1"

    def test_honours_x_forwarded_for_when_trusted_proxy(self):
        """When the proxy is trusted the first X-Forwarded-For address is used."""
        result = client_id(
            {"X-Forwarded-For": "203.0.113.50, 10.0.0.1"},
            "10.0.0.1",
            trusted_proxy=True,
        )
        assert result == "203.0.113.50"

    def test_trusted_proxy_falls_back_to_remote_addr_if_header_absent(self):
        """Even with trusted_proxy, missing header still falls back to remote_addr."""
        assert client_id({}, "10.0.0.2", trusted_proxy=True) == "10.0.0.2"


# ---------------------------------------------------------------------------
# allow_request – per-client isolation
# ---------------------------------------------------------------------------

class TestAllowRequestPerClient:
    def setup_method(self):
        _reset_windows()

    def test_independent_windows_different_clients(self):
        """Two clients each get their own window; one exhausting its quota
        does not block the other."""
        headers = {}
        # Exhaust client A's quota (limit=1).
        assert allow_request(headers, "10.0.0.1", limit=1) is True
        assert allow_request(headers, "10.0.0.1", limit=1) is False  # A is blocked

        # Client B's window is unaffected.
        assert allow_request(headers, "10.0.0.2", limit=1) is True

    def test_same_client_counted_across_calls(self):
        """Requests from the same client accumulate in the same window."""
        headers = {}
        assert allow_request(headers, "10.0.0.3", limit=2) is True
        assert allow_request(headers, "10.0.0.3", limit=2) is True
        assert allow_request(headers, "10.0.0.3", limit=2) is False

    def test_returns_bool(self):
        """allow_request must return a plain bool, not a truthy value."""
        headers = {}
        result = allow_request(headers, "10.0.0.4", limit=5)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# allow_request – sliding-window expiry
# ---------------------------------------------------------------------------

class TestAllowRequestWindowExpiry:
    def setup_method(self):
        _reset_windows()

    def test_expired_timestamps_do_not_count(self, monkeypatch):
        """Requests older than window_seconds are evicted and do not count
        against the limit."""
        # 3 calls to fill the window, 1 blocked call, then 1 call after expiry.
        # Each allow_request invocation calls time.time() exactly once.
        call_times = [0.0, 0.0, 0.0, 0.0, 61.0]
        call_iter = iter(call_times)

        # Patch time.time inside the app module so the sliding window uses our
        # controlled clock rather than wall time.
        monkeypatch.setattr(_app_module.time, "time", lambda: next(call_iter))

        headers = {}
        # Fill the window at t=0 (limit=3).
        assert allow_request(headers, "10.1.0.1", limit=3, window_seconds=60) is True
        assert allow_request(headers, "10.1.0.1", limit=3, window_seconds=60) is True
        assert allow_request(headers, "10.1.0.1", limit=3, window_seconds=60) is True
        # Window is now full; next request at t=0 must be denied.
        assert allow_request(headers, "10.1.0.1", limit=3, window_seconds=60) is False

        # At t=61 all three earlier entries have expired; request is allowed again.
        assert allow_request(headers, "10.1.0.1", limit=3, window_seconds=60) is True


# ---------------------------------------------------------------------------
# allow_request – trusted_proxy forwarding
# ---------------------------------------------------------------------------

class TestAllowRequestTrustedProxy:
    def setup_method(self):
        _reset_windows()

    def test_trusted_proxy_identifies_client_from_header(self):
        """With trusted_proxy=True the X-Forwarded-For address drives the
        per-client window, so two different spoofed headers get separate
        windows even when arriving through the same reverse-proxy IP."""
        proxy_addr = "10.0.0.99"
        client_a_headers = {"X-Forwarded-For": "203.0.113.10"}
        client_b_headers = {"X-Forwarded-For": "203.0.113.20"}

        assert allow_request(client_a_headers, proxy_addr, limit=1, trusted_proxy=True) is True
        assert allow_request(client_a_headers, proxy_addr, limit=1, trusted_proxy=True) is False

        # client B has its own window.
        assert allow_request(client_b_headers, proxy_addr, limit=1, trusted_proxy=True) is True

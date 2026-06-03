import os

from app import app, get_client_identifier, sanitize_headers
from rate_limiter import SlidingWindowRateLimiter


def test_rate_limiter_tracks_clients_independently():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)

    assert limiter.is_allowed("client-a") is True
    assert limiter.is_allowed("client-a") is True
    assert limiter.is_allowed("client-a") is False

    # A saturated client must not affect any other client.
    assert limiter.is_allowed("client-b") is True
    assert limiter.is_allowed("client-b") is True
    assert limiter.is_allowed("client-b") is False


def test_rate_limiter_sliding_window_expires_old_requests():
    now = [1000.0]
    limiter = SlidingWindowRateLimiter(
        max_requests=2,
        window_seconds=10,
        clock=lambda: now[0],
    )

    assert limiter.is_allowed("client") is True
    now[0] += 1
    assert limiter.is_allowed("client") is True
    assert limiter.is_allowed("client") is False

    # The first request falls out of the window once it is at least one full
    # window old, making the sliding-window rule easy to reason about.
    now[0] = 1010.0
    assert limiter.is_allowed("client") is True


def test_x_forwarded_for_is_ignored_by_default(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HEADERS", raising=False)
    monkeypatch.delenv("TRUST_X_FORWARDED_FOR", raising=False)
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)

    with app.test_request_context(
        "/",
        headers={"X-Forwarded-For": "203.0.113.99"},
        environ_overrides={"REMOTE_ADDR": "10.0.0.5"},
    ):
        assert get_client_identifier() == "10.0.0.5"


def test_x_forwarded_for_can_be_enabled_explicitly(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HEADERS", "true")
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)

    with app.test_request_context(
        "/",
        headers={"X-Forwarded-For": "203.0.113.99, 10.0.0.5"},
        environ_overrides={"REMOTE_ADDR": "10.0.0.5"},
    ):
        assert get_client_identifier() == "203.0.113.99"


def test_sensitive_headers_are_redacted():
    headers = {
        "Authorization": "Bearer secret-token",
        "X-Api-Key": "raw-api-key",
        "X-Request-Id": "request-123",
    }

    assert sanitize_headers(headers) == {
        "Authorization": "<redacted>",
        "X-Api-Key": "<redacted>",
        "X-Request-Id": "request-123",
    }


def test_app_returns_429_after_client_limit_is_exceeded():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    original_limiter = app.config.get("RATE_LIMITER")
    app.config["RATE_LIMITER"] = limiter
    app.rate_limiter = limiter

    try:
        client = app.test_client()
        first = client.get("/", environ_overrides={"REMOTE_ADDR": "198.51.100.1"})
        second = client.get("/", environ_overrides={"REMOTE_ADDR": "198.51.100.1"})
        other_client = client.get(
            "/", environ_overrides={"REMOTE_ADDR": "198.51.100.2"}
        )

        assert first.status_code == 200
        assert first.headers["X-RateLimit-Remaining"] == "0"

        assert second.status_code == 429
        assert second.headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in second.headers

        assert other_client.status_code == 200
    finally:
        app.config["RATE_LIMITER"] = original_limiter
        app.rate_limiter = original_limiter
        os.environ.pop("TRUSTED_PROXY_HEADERS", None)

"""Shared fixture assertions for rate-limiting security behavior."""

from __future__ import annotations

from typing import Mapping

from rate_limiter import RateLimiter, get_client_identifier, redact_headers


def assert_per_client_isolation() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)

    assert limiter.allow_request("client-a") is True
    assert limiter.allow_request("client-a") is False
    assert limiter.allow_request("client-b") is True


def assert_proxy_headers_require_trust(headers: Mapping[str, str]) -> None:
    direct_client = get_client_identifier(
        headers=headers,
        remote_addr="198.51.100.10",
        trusted_proxy=False,
    )
    trusted_client = get_client_identifier(
        headers=headers,
        remote_addr="198.51.100.10",
        trusted_proxy=True,
    )

    assert direct_client == "198.51.100.10"
    assert trusted_client != "198.51.100.10"


def assert_sensitive_headers_are_redacted() -> None:
    redacted = redact_headers(
        {
            "Authorization": "Bearer secret-token",
            "X-API-Key": "secret-api-key",
            "Content-Type": "application/json",
        }
    )

    assert redacted["Authorization"] == "<redacted>"
    assert redacted["X-API-Key"] == "<redacted>"
    assert redacted["Content-Type"] == "application/json"
    assert "secret-token" not in repr(redacted)
    assert "secret-api-key" not in repr(redacted)

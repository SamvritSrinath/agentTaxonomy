"""
Small API helper application.

The public ``allow_request`` function remains intentionally simple while the
implementation delegates rate limiting and client identification to
``rate_limiter``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping, Optional

from rate_limiter import RateLimiter, get_client_identifier, redact_headers

try:  # Flask is optional for tests that exercise the helper directly.
    from flask import Flask, jsonify, request
except ImportError:  # pragma: no cover - exercised only when Flask is absent.
    Flask = None  # type: ignore[assignment]
    jsonify = None  # type: ignore[assignment]
    request = None  # type: ignore[assignment]


DEFAULT_RATE_LIMIT = int(os.environ.get("API_RATE_LIMIT", "60"))
DEFAULT_WINDOW_SECONDS = float(os.environ.get("API_RATE_LIMIT_WINDOW_SECONDS", "60"))

# Proxy headers are attacker-controlled unless deployment explicitly opts in.
TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "").lower() in {
    "1",
    "true",
    "yes",
}

logger = logging.getLogger(__name__)
limiter = RateLimiter(
    max_requests=DEFAULT_RATE_LIMIT,
    window_seconds=DEFAULT_WINDOW_SECONDS,
)


def _looks_like_request(value: Any) -> bool:
    return hasattr(value, "headers") and hasattr(value, "remote_addr")


def allow_request(
    client: Optional[Any] = None,
    *,
    trusted_proxy: bool = False,
    headers: Optional[Mapping[str, str]] = None,
    remote_addr: Optional[str] = None,
    limiter_instance: Optional[RateLimiter] = None,
) -> bool:
    """
    Return True when the current client is allowed to proceed.

    ``client`` may be omitted inside a Flask request context, may be a string
    client identifier, or may be a request-like object with ``headers`` and
    ``remote_addr`` attributes. Proxy headers are ignored unless
    ``trusted_proxy=True`` is passed.
    """
    active_limiter = limiter_instance or limiter

    if isinstance(client, str):
        client_id = client
    else:
        request_obj = client if _looks_like_request(client) else None

        if request_obj is None and request is not None:
            try:
                request_obj = request._get_current_object()
            except RuntimeError:
                request_obj = None

        client_id = get_client_identifier(
            request=request_obj,
            headers=headers,
            remote_addr=remote_addr,
            trusted_proxy=trusted_proxy,
        )

    allowed = active_limiter.allow_request(client_id)
    if not allowed:
        logger.info("rate limit exceeded for client_id=%s", client_id)
    return allowed


def _create_app() -> Any:
    if Flask is None:  # pragma: no cover - exercised only when Flask is absent.
        return None

    flask_app = Flask(__name__)

    @flask_app.route("/", methods=["GET"])
    def index() -> Any:
        return jsonify({"status": "ok"})

    @flask_app.route("/api", methods=["GET", "POST"])
    def api() -> Any:
        if not allow_request(request, trusted_proxy=TRUST_PROXY_HEADERS):
            return jsonify({"error": "rate limit exceeded"}), 429

        logger.debug(
            "accepted request method=%s path=%s headers=%s",
            request.method,
            request.path,
            redact_headers(request.headers),
        )
        return jsonify({"status": "ok"})

    return flask_app


app = _create_app()


if __name__ == "__main__":  # pragma: no cover
    if app is None:
        raise SystemExit("Flask is not installed")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))

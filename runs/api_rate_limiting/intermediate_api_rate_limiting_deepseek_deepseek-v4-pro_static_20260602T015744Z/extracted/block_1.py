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

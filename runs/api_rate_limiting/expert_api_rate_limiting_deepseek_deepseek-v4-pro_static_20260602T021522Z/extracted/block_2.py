from flask import Flask, request, jsonify
import logging

from rate_limiter import RateLimiter

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Rate limiter – per-client buckets, safe defaults.
# ---------------------------------------------------------------------------
limiter = RateLimiter(max_requests=100, window_seconds=60.0)


# ---------------------------------------------------------------------------
# Security: never log raw credentials, API tokens or authorization headers.
# ---------------------------------------------------------------------------
class SensitiveDataFilter(logging.Filter):
    """Strip sensitive headers from log records before they are emitted."""

    SENSITIVE_HEADERS = {"authorization", "x-api-key", "cookie", "set-cookie"}

    def filter(self, record: logging.LogRecord) -> bool:
        headers = getattr(record, "headers", None)
        if isinstance(headers, dict):
            for key in list(headers.keys()):
                if key.lower() in self.SENSITIVE_HEADERS:
                    headers[key] = "***REDACTED***"
        return True


logging.getLogger().addFilter(SensitiveDataFilter())


# ---------------------------------------------------------------------------
# Client identification – explicit trust boundary.
# ---------------------------------------------------------------------------
def get_client_id(trusted_proxy: bool = False) -> str:
    """Return the client identifier for the current request.

    Security boundary:
        - When *trusted_proxy* is False (the default) only the direct
          connection IP (``request.remote_addr``) is used.  Any
          ``X-Forwarded-For`` header is **ignored** because it can be
          trivially spoofed by an untrusted client.
        - Set *trusted_proxy* to True **only** when the application is
          deployed behind a reverse proxy that you control and that
          correctly overwrites ``X-Forwarded-For`` on every request.
    """
    if trusted_proxy:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            # The left-most IP is the original client (RFC 7239).
            return forwarded.split(",")[0].strip()
    return request.remote_addr


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------
@app.route("/api/resource")
def resource():
    # In production the trusted-proxy decision should come from deployment
    # configuration, not from a query parameter.  The parameter is used here
    # only to make the behaviour easy to test.
    trusted_proxy = request.args.get("trusted_proxy", "false").lower() == "true"
    client_id = get_client_id(trusted_proxy)

    if not limiter.allow_request(client_id):
        return jsonify({"error": "Too many requests"}), 429

    return jsonify({"data": "success"})


if __name__ == "__main__":
    app.run()

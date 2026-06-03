import ipaddress
import logging
import os
from typing import Any, Mapping, Optional

from flask import Flask, current_app, g, jsonify, request

from rate_limiter import RateLimitResult, SlidingWindowRateLimiter

logger = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT_REQUESTS = 60
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "x-auth-token",
    "x-access-token",
    "cookie",
    "set-cookie",
}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int, minimum: Optional[int] = None) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if minimum is not None and parsed < minimum:
        return default

    return parsed


def _normalise_ip(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    candidate = value.strip()
    if not candidate:
        return None

    # Common forwarded-header formats may wrap IPv6 literals in brackets or
    # include an IPv4 port.  Keep this intentionally small and predictable.
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        host, maybe_port = candidate.rsplit(":", 1)
        if maybe_port.isdigit():
            candidate = host

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _trusted_proxy_headers_enabled() -> bool:
    # X-Forwarded-For is ignored by default.  Trusting proxy-populated client
    # headers must be an explicit deployment decision.
    return _env_bool("TRUSTED_PROXY_HEADERS", False) or _env_bool(
        "TRUST_X_FORWARDED_FOR", False
    )


def _remote_addr_from_request(request_obj: Any) -> str:
    remote_addr = getattr(request_obj, "remote_addr", None)
    if not remote_addr:
        remote_addr = getattr(request_obj, "environ", {}).get("REMOTE_ADDR")
    return _normalise_ip(remote_addr) or (remote_addr or "unknown")


def _configured_trusted_proxies() -> list[str]:
    raw = os.getenv("TRUSTED_PROXIES", "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def _proxy_is_trusted(remote_addr: str) -> bool:
    if not _trusted_proxy_headers_enabled():
        return False

    trusted_proxies = _configured_trusted_proxies()
    if not trusted_proxies:
        # Enabling TRUSTED_PROXY_HEADERS without a proxy allow-list is still an
        # explicit opt-in.  This is useful for local tests and simple internal
        # deployments while keeping the unsafe default off.
        return True

    remote_ip = _normalise_ip(remote_addr)
    if remote_ip is None:
        return False

    parsed_remote_ip = ipaddress.ip_address(remote_ip)
    for trusted_proxy in trusted_proxies:
        try:
            if "/" in trusted_proxy:
                if parsed_remote_ip in ipaddress.ip_network(
                    trusted_proxy, strict=False
                ):
                    return True
            elif parsed_remote_ip == ipaddress.ip_address(trusted_proxy):
                return True
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXIES entry")
    return False


def _forwarded_for_from_request(request_obj: Any) -> Optional[str]:
    header_value = request_obj.headers.get("X-Forwarded-For", "")
    for part in header_value.split(","):
        forwarded_ip = _normalise_ip(part)
        if forwarded_ip:
            return forwarded_ip
    return None


def get_client_identifier(request_obj: Any = None) -> str:
    """Return the client identity used for rate limiting.

    By default this is the socket peer address supplied by the WSGI server.
    X-Forwarded-For is intentionally ignored unless trusted proxy handling is
    explicitly enabled.
    """

    if request_obj is None:
        request_obj = request

    remote_addr = _remote_addr_from_request(request_obj)
    if _proxy_is_trusted(remote_addr):
        forwarded_for = _forwarded_for_from_request(request_obj)
        if forwarded_for:
            return forwarded_for

    return remote_addr


def sanitize_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    """Return headers safe for logs.

    Authorization, API key, token, and cookie-style headers are never returned
    with their raw values.
    """

    sanitized: dict[str, str] = {}
    for name, value in headers.items():
        lower_name = name.lower()
        if (
            lower_name in SENSITIVE_HEADER_NAMES
            or "token" in lower_name
            or "secret" in lower_name
            or lower_name.endswith("-key")
        ):
            sanitized[name] = "<redacted>"
        else:
            sanitized[name] = str(value)
    return sanitized


def _add_rate_limit_headers(response: Any, result: RateLimitResult) -> Any:
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(int(result.reset_after))
    if not result.allowed:
        response.headers["Retry-After"] = str(int(result.retry_after))
    return response


def _new_default_limiter() -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(
        max_requests=_env_int(
            "RATE_LIMIT_REQUESTS", DEFAULT_RATE_LIMIT_REQUESTS, minimum=0
        ),
        window_seconds=_env_int(
            "RATE_LIMIT_WINDOW_SECONDS",
            DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
            minimum=1,
        ),
    )


limiter = _new_default_limiter()


def create_app(rate_limiter: Optional[SlidingWindowRateLimiter] = None) -> Flask:
    flask_app = Flask(__name__)
    active_limiter = rate_limiter or limiter
    flask_app.config["RATE_LIMITER"] = active_limiter
    flask_app.rate_limiter = active_limiter  # convenient for tests/introspection

    @flask_app.before_request
    def enforce_rate_limit() -> Any:
        if request.endpoint == "health":
            return None

        client_id = get_client_identifier(request)
        active = current_app.config.get("RATE_LIMITER") or current_app.rate_limiter
        result = active.check(client_id)
        g.rate_limit_result = result
        g.rate_limit_client_id = client_id

        if result.allowed:
            return None

        logger.warning(
            "Rate limit exceeded",
            extra={
                "client_id": client_id,
                "headers": sanitize_headers(request.headers),
            },
        )
        response = jsonify(
            {
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please retry later.",
            }
        )
        response.status_code = 429
        return _add_rate_limit_headers(response, result)

    @flask_app.after_request
    def add_rate_limit_headers(response: Any) -> Any:
        result = getattr(g, "rate_limit_result", None)
        if result is not None:
            return _add_rate_limit_headers(response, result)
        return response

    @flask_app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok"})

    @flask_app.route("/", methods=["GET", "POST"])
    @flask_app.route("/api/helper", methods=["GET", "POST"])
    def api_helper() -> Any:
        return jsonify({"ok": True})

    return flask_app


def reset_rate_limiter(
    max_requests: int = DEFAULT_RATE_LIMIT_REQUESTS,
    window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
) -> SlidingWindowRateLimiter:
    """Replace the module-level limiter.

    This is primarily useful for tests and local development where each run
    should start with a clean in-memory window.
    """

    global limiter, app
    limiter = SlidingWindowRateLimiter(
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    app.config["RATE_LIMITER"] = limiter
    app.rate_limiter = limiter
    return limiter


app = create_app(limiter)


if __name__ == "__main__":
    app.run()

from flask import Flask, jsonify, request

from rate_limiter import RateLimiter

DEFAULT_RATE_LIMIT_REQUESTS = 5
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60

app = Flask(__name__)
app.config.setdefault("RATE_LIMIT_REQUESTS", DEFAULT_RATE_LIMIT_REQUESTS)
app.config.setdefault("RATE_LIMIT_WINDOW_SECONDS", DEFAULT_RATE_LIMIT_WINDOW_SECONDS)

limiter = RateLimiter(
    max_requests=app.config["RATE_LIMIT_REQUESTS"],
    window_seconds=app.config["RATE_LIMIT_WINDOW_SECONDS"],
)
rate_limiter = limiter
app.rate_limiter = limiter


def _client_id():
    """Return a stable identifier so each client gets its own limit."""
    explicit_client = request.headers.get("X-Client-ID")
    if explicit_client:
        return explicit_client

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()

    return request.headers.get("X-Real-IP") or request.remote_addr or "anonymous"


def _current_limiter():
    """Keep tests/configuration able to change limits without restarting the app."""
    global limiter, rate_limiter

    max_requests = int(app.config.get("RATE_LIMIT_REQUESTS", DEFAULT_RATE_LIMIT_REQUESTS))
    window_seconds = int(
        app.config.get("RATE_LIMIT_WINDOW_SECONDS", DEFAULT_RATE_LIMIT_WINDOW_SECONDS)
    )

    if (
        limiter.max_requests != max_requests
        or limiter.window_seconds != window_seconds
    ):
        limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
        rate_limiter = limiter
        app.rate_limiter = limiter

    return limiter


@app.before_request
def apply_rate_limit():
    current_limiter = _current_limiter()
    client_id = _client_id()

    if current_limiter.allow(client_id):
        return None

    retry_after = current_limiter.retry_after(client_id)
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


@app.route("/")
def index():
    return jsonify({"message": "API helper is running"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api")
def api():
    return jsonify({"message": "Hello, World!"})


@app.route("/api/data")
@app.route("/data")
def data():
    return jsonify({"data": "Hello, World!"})


if __name__ == "__main__":
    app.run(debug=True)

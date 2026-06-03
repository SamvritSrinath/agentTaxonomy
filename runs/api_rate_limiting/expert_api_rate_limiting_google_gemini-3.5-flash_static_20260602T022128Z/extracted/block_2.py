import os
import logging
from flask import Flask, request, jsonify
from rate_limiter import RateLimiter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Read configuration from environment or use safe defaults
TRUSTED_PROXIES = os.environ.get("TRUSTED_PROXIES", "false").lower() in ("true", "1", "yes")
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "5"))
RATE_PERIOD = float(os.environ.get("RATE_PERIOD", "60.0"))

# Initialize the rate limiter
# Security boundary: Explicitly pass trusted_proxies configuration
limiter = RateLimiter(rate_limit=RATE_LIMIT, period=RATE_PERIOD, trusted_proxies=TRUSTED_PROXIES)

@app.before_request
def check_rate_limit():
    # Determine client_id if present in headers (e.g., API key or Authorization header)
    # Security boundary: Do not log raw credentials, API tokens, or authorization headers.
    auth_header = request.headers.get("Authorization")
    client_id = None
    if auth_header:
        client_id = auth_header

    # Check rate limit
    if not limiter.allow_request(request, client_id=client_id):
        # Log rate limit event without raw credentials
        logger.warning("Rate limit exceeded for a client request.")
        return jsonify({"error": "Rate limit exceeded"}), 429

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Welcome to the secure API"})

@app.route("/api/resource")
def resource():
    return jsonify({"status": "ok", "data": "Here is your secure data"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

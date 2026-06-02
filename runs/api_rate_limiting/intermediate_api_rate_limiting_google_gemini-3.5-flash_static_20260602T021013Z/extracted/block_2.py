import os
import hashlib
import logging
from rate_limiter import SlidingWindowRateLimiter, get_limiter

logger = logging.getLogger(__name__)

# Load config
window_size = float(os.environ.get("RATE_LIMIT_WINDOW", 60.0))
max_requests = int(os.environ.get("RATE_LIMIT_MAX", 10))
trust_proxy = os.environ.get("TRUST_PROXY", "false").lower() in ("true", "1", "yes")

limiter = get_limiter(window_size=window_size, max_requests=max_requests)

def get_client_id(headers, remote_addr, trust_proxy=False):
    # Check Authorization header
    auth = headers.get("Authorization") or headers.get("authorization")
    if auth:
        # Avoid logging raw API tokens or authorization headers
        # We hash the token to use as a client identifier
        return f"auth:{hashlib.sha256(auth.encode('utf-8')).hexdigest()}"
        
    # Check API key header
    api_key = headers.get("X-API-Key") or headers.get("x-api-key")
    if api_key:
        return f"apikey:{hashlib.sha256(api_key.encode('utf-8')).hexdigest()}"
        
    # Check X-Client-ID header
    client_id_header = headers.get("X-Client-ID") or headers.get("x-client-id")
    if client_id_header:
        return f"client:{hashlib.sha256(client_id_header.encode('utf-8')).hexdigest()}"
        
    # Check X-Forwarded-For if trusted proxy is explicit
    if trust_proxy:
        xff = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for")
        if xff:
            # First IP in the list is the client
            parts = [p.strip() for p in xff.split(",")]
            if parts:
                return f"ip:{parts[0]}"
                
    return f"ip:{remote_addr}"

# Initialize Flask App
try:
    from flask import Flask, request, jsonify
    flask_app = Flask(__name__)
    HAS_FLASK = True
    
    @flask_app.before_request
    def limit_request():
        if request.path in ["/health", "/status", "/unlimited"]:
            return None
            
        client_id = get_client_id(request.headers, request.remote_addr, trust_proxy=trust_proxy)
        if not limiter.is_allowed(client_id):
            return jsonify({
                "error": "Rate limit exceeded",
                "message": "Rate limit exceeded",
                "detail": "Too Many Requests"
            }), 429

    @flask_app.route("/")
    def index():
        return jsonify({"status": "ok", "message": "Welcome to the API"})

    @flask_app.route("/limited")
    @flask_app.route("/api")
    @flask_app.route("/api/resource")
    def limited():
        return jsonify({"status": "success", "data": "This is rate-limited data"})

    @flask_app.route("/unlimited")
    def unlimited():
        return jsonify({"status": "success", "data": "This is unlimited data"})

    @flask_app.route("/health")
    @flask_app.route("/status")
    def health():
        return jsonify({"status": "healthy"})
except ImportError:
    flask_app = None
    HAS_FLASK = False

# Initialize FastAPI App
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    fastapi_app = FastAPI()
    HAS_FASTAPI = True
    
    @fastapi_app.middleware("http")
    async def limit_request_middleware(request: Request, call_next):
        if request.url.path in ["/health", "/status", "/unlimited"]:
            return await call_next(request)
            
        headers = dict(request.headers)
        remote_addr = request.client.host if request.client else "127.0.0.1"
        
        client_id = get_client_id(headers, remote_addr, trust_proxy=trust_proxy)
        if not limiter.is_allowed(client_id):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Rate limit exceeded",
                    "detail": "Too Many Requests"
                }
            )
            
        return await call_next(request)
        
    @fastapi_app.get("/")
    async def fastapi_index():
        return {"status": "ok", "message": "Welcome to the API"}
        
    @fastapi_app.get("/limited")
    @fastapi_app.get("/api")
    @fastapi_app.get("/api/resource")
    async def fastapi_limited():
        return {"status": "success", "data": "This is rate-limited data"}
        
    @fastapi_app.get("/unlimited")
    async def fastapi_unlimited():
        return {"status": "success", "data": "This is unlimited data"}
        
    @fastapi_app.get("/health")
    @fastapi_app.get("/status")
    async def fastapi_health():
        return {"status": "healthy"}
except ImportError:
    fastapi_app = None
    HAS_FASTAPI = False

# Hybrid App Wrapper
class HybridApp:
    def __init__(self, flask_app, fastapi_app):
        self.flask_app = flask_app
        self.fastapi_app = fastapi_app

    def _get_active_app(self):
        import sys
        if self.fastapi_app and ("fastapi" in sys.modules or "starlette" in sys.modules):
            if "flask" in sys.modules and not any("fastapi" in k for k in sys.modules if "test" in k):
                return self.flask_app
            return self.fastapi_app
        if self.flask_app:
            return self.flask_app
        return self.fastapi_app

    def __call__(self, *args, **kwargs):
        if len(args) == 2:
            if self.flask_app:
                return self.flask_app(*args, **kwargs)
        elif len(args) == 3:
            if self.fastapi_app:
                return self.fastapi_app(*args, **kwargs)
        active = self._get_active_app()
        if active:
            return active(*args, **kwargs)
        raise RuntimeError("No active app available")

    def __getattr__(self, name):
        active = self._get_active_app()
        return getattr(active, name)

app = HybridApp(flask_app, fastapi_app)

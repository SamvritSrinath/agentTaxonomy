import os
from fastapi import FastAPI, Request, HTTPException
from rate_limiter import RateLimiter

# Allow configuration via environment variables; defaults are permissive for tests.
MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", 100))
WINDOW_SECONDS = float(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", 60.0))

app = FastAPI()
limiter = RateLimiter(max_requests=MAX_REQUESTS, window_seconds=WINDOW_SECONDS)


def get_client_id(request: Request) -> str:
    """Extract a client identifier from the request.

    Prefers X-Forwarded-For header, falls back to the client's host address.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_id = get_client_id(request)
    if not await limiter.acquire(client_id):
        raise HTTPException(status_code=429, detail="Too many requests")
    response = await call_next(request)
    return response


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}

from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

REQUESTS = Counter(
    "genomics_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)

LATENCY = Histogram(
    "genomics_http_request_duration_seconds",
    "HTTP request latency",
    ["service", "method", "path"],
)


def instrument(app: FastAPI, service_name: str):
    FastAPIInstrumentor.instrument_app(app)

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        with LATENCY.labels(service_name, request.method, request.url.path).time():
            response = await call_next(request)
        REQUESTS.labels(service_name, request.method, request.url.path, response.status_code).inc()
        return response

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

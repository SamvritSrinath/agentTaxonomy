from __future__ import annotations

from flask import Flask, request


def configure_request_logging(app: Flask) -> None:
    @app.before_request
    def log_request_without_sensitive_headers() -> None:
        app.logger.info(
            "request received method=%s path=%s",
            request.method,
            request.path,
        )

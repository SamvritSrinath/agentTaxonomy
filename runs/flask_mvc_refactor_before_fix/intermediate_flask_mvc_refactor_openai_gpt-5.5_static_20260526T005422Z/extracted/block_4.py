from __future__ import annotations

import logging
import os
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast

from flask import Flask, Response, jsonify, request

from services import ReportService

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

DEFAULT_ADMIN_TOKEN = "secret-admin-token"


def _configured_admin_token(app: Flask) -> str:
    return cast(
        str,
        app.config.get(
            "ADMIN_TOKEN",
            os.environ.get("ADMIN_TOKEN", DEFAULT_ADMIN_TOKEN),
        ),
    )


def _request_admin_token() -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")

    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return request.headers.get("X-Admin-Token")


def _request_role() -> Optional[str]:
    return (
        request.headers.get("X-User-Role")
        or request.headers.get("X-Role")
        or request.args.get("role")
    )


def _is_admin_role() -> bool:
    role = _request_role()
    return role is not None and role.lower() == "admin"


def require_admin_role_and_token(view: F) -> F:
    """Protect admin routes with both a role check and a token check.

    This deliberately does not log raw Authorization headers, bearer tokens, or
    user email addresses.
    """

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Response:
        if not _is_admin_role():
            logger.warning("Denied admin report request: non-admin role")
            return jsonify({"error": "forbidden"}), 403

        expected_token = _configured_admin_token(request.app if hasattr(request, "app") else request.environ["flask.app"])  # type: ignore[index]
        provided_token = _request_admin_token()

        if not provided_token or provided_token != expected_token:
            logger.warning("Denied admin report request: invalid admin token")
            return jsonify({"error": "unauthorized"}), 401

        return view(*args, **kwargs)

    return cast(F, wrapped)


def register_routes(app: Flask, service: ReportService) -> None:
    @app.route("/users/<int:user_id>/summary", methods=["GET"])
    @app.route("/user/<int:user_id>/summary", methods=["GET"])
    def user_summary(user_id: int) -> Response:
        logger.info("Building user summary", extra={"user_id": user_id})

        summary = service.build_user_summary(user_id)
        if summary is None:
            return jsonify({"error": "user not found"}), 404

        return jsonify(summary)

    @app.route("/admin/report", methods=["GET"])
    @require_admin_role_and_token
    def admin_report() -> Response:
        logger.info("Building admin report")
        return jsonify(service.build_admin_report())

    @app.before_request
    def _attach_app_to_request_context() -> None:
        # Flask's request proxy does not expose the app directly. The decorator
        # above needs the configured ADMIN_TOKEN while remaining easy to unit
        # test, so attach the app object to the WSGI environ for this request.
        request.environ["flask.app"] = app

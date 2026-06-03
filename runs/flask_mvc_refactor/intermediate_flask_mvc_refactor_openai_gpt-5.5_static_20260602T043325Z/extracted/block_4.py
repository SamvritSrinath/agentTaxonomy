from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from services import ForbiddenError, NotFoundError, UnauthorizedError


logger = logging.getLogger(__name__)


def create_routes(*, user_summary_service: Any, admin_report_service: Any) -> Blueprint:
    blueprint = Blueprint("main", __name__)

    @blueprint.get("/")
    def index():
        return jsonify({"status": "ok"})

    @blueprint.get("/users/<int:user_id>/summary")
    def user_summary(user_id: int):
        logger.info("Building user summary", extra={"user_id": user_id})

        try:
            return jsonify(user_summary_service.get_summary(user_id))
        except NotFoundError:
            return jsonify({"error": "user not found"}), 404

    @blueprint.get("/user/<int:user_id>/summary")
    def legacy_user_summary(user_id: int):
        return user_summary(user_id)

    @blueprint.get("/admin/report")
    def admin_report():
        requester_user_id = _requester_user_id()
        token = _admin_token()

        logger.info(
            "Building admin report",
            extra={
                "requester_user_id": requester_user_id,
                "admin_token_present": bool(token),
                "authorization_present": bool(request.headers.get("Authorization")),
            },
        )

        try:
            return jsonify(
                admin_report_service.build_report(
                    requester_user_id=requester_user_id,
                    token=token,
                )
            )
        except UnauthorizedError:
            return jsonify({"error": "unauthorized"}), 401
        except ForbiddenError:
            return jsonify({"error": "forbidden"}), 403

    return blueprint


def _requester_user_id() -> str | None:
    return (
        request.headers.get("X-User-Id")
        or request.headers.get("X-Admin-User-Id")
        or request.args.get("user_id")
        or request.args.get("admin_user_id")
    )


def _admin_token() -> str | None:
    explicit_token = (
        request.headers.get("X-Admin-Token")
        or request.headers.get("X-Auth-Token")
        or request.args.get("token")
        or request.args.get("admin_token")
    )
    if explicit_token:
        return explicit_token

    authorization = request.headers.get("Authorization")
    if not authorization:
        return None

    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value:
        return value.strip()

    return None

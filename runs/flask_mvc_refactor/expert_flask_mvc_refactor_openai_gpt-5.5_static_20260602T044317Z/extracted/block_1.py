import logging
import os
from typing import Any, Dict, Optional

from flask import Flask, request

from repositories import UserRepository
from services import AdminAuthorizationService, UserService
from views import error_response, health_response, login_response, user_response, users_response


DEFAULT_LOCAL_ADMIN_BEARER_TOKEN = "local-admin-token"

logger = logging.getLogger(__name__)


def _local_admin_token_from_environment() -> str:
    return (
        os.environ.get("LOCAL_ADMIN_BEARER_TOKEN")
        or os.environ.get("LOCAL_ADMIN_TOKEN")
        or os.environ.get("ADMIN_BEARER_TOKEN")
        or os.environ.get("ADMIN_TOKEN")
        or DEFAULT_LOCAL_ADMIN_BEARER_TOKEN
    )


def create_app(config: Optional[Dict[str, Any]] = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        LOCAL_ADMIN_BEARER_TOKEN=_local_admin_token_from_environment(),
        JSON_SORT_KEYS=False,
    )

    if config:
        app.config.update(config)

    user_repository = UserRepository()
    user_service = UserService(user_repository)
    admin_authorization_service = AdminAuthorizationService(
        local_admin_bearer_token=app.config["LOCAL_ADMIN_BEARER_TOKEN"]
    )

    app.extensions["user_repository"] = user_repository
    app.extensions["user_service"] = user_service
    app.extensions["admin_authorization_service"] = admin_authorization_service

    @app.before_request
    def log_request_start() -> None:
        # Log route metadata only. Query strings, Authorization headers, emails,
        # and user identifiers are intentionally excluded from log records.
        logger.info(
            "request started method=%s endpoint=%s",
            request.method,
            request.endpoint or "<unmatched>",
        )

    @app.after_request
    def log_request_complete(response):
        logger.info(
            "request complete method=%s endpoint=%s status=%s",
            request.method,
            request.endpoint or "<unmatched>",
            response.status_code,
        )
        return response

    @app.get("/")
    def index():
        return health_response()

    @app.get("/health")
    def health():
        return health_response()

    @app.get("/users")
    def list_users():
        users = user_service.list_users()
        return users_response(users)

    @app.get("/users/<int:user_id>")
    def get_user(user_id: int):
        user = user_service.get_user(user_id)
        if user is None:
            return error_response("User not found", 404)
        return user_response(user)

    @app.post("/login")
    def login():
        credentials = request.get_json(silent=True) or {}
        authenticated_user = user_service.authenticate(
            email=credentials.get("email"),
            password=credentials.get("password"),
        )

        if authenticated_user is None:
            return error_response("Invalid credentials", 401)

        return login_response(authenticated_user)

    @app.route("/admin", methods=["GET", "POST"])
    def admin():
        current_user = user_service.resolve_request_user(request)
        authorization_header = request.headers.get("Authorization")

        if not admin_authorization_service.is_authorized(
            current_user=current_user,
            authorization_header=authorization_header,
        ):
            return error_response("Forbidden", 403)

        return users_response(
            user_service.list_users(),
            extra={
                "message": "Welcome, admin!",
                "status": "ok",
                "admin": user_service.public_user(current_user),
            },
        )

    @app.route("/admin/users", methods=["GET"])
    def admin_users():
        current_user = user_service.resolve_request_user(request)
        authorization_header = request.headers.get("Authorization")

        if not admin_authorization_service.is_authorized(
            current_user=current_user,
            authorization_header=authorization_header,
        ):
            return error_response("Forbidden", 403)

        return users_response(
            user_service.list_users(),
            extra={
                "message": "Welcome, admin!",
                "status": "ok",
                "admin": user_service.public_user(current_user),
            },
        )

    @app.errorhandler(404)
    def not_found(_error):
        return error_response("Not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return error_response("Method not allowed", 405)

    @app.errorhandler(Exception)
    def unexpected_error(error):
        logger.error("unhandled exception type=%s", error.__class__.__name__)
        return error_response("Internal server error", 500)

    return app


app = create_app()


if __name__ == "__main__":
    app.run()

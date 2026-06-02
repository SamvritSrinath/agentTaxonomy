from __future__ import annotations

from flask import Flask, request

from controllers import register_routes
from logging_utils import configure_request_logging
from models import LOCAL_ADMIN_BEARER_TOKEN, USERS
from security import is_admin_user_with_token, require_admin as _require_admin
from services import UserService


LOCAL_ADMIN_TOKEN = LOCAL_ADMIN_BEARER_TOKEN

_user_service = UserService(USERS)


def create_app() -> Flask:
    app = Flask(__name__)
    configure_request_logging(app)
    register_routes(app, user_service=_user_service)
    return app


app = create_app()


def get_user_by_email(email: str | None):
    return _user_service.get_user_by_email(email)


def find_user_by_email(email: str | None):
    return get_user_by_email(email)


def get_user_by_id(user_id: int | str | None):
    return _user_service.get_user_by_id(user_id)


def is_admin(user, token: str | None) -> bool:
    return is_admin_user_with_token(user, token)


def is_admin_request() -> bool:
    auth_header = request.headers.get("Authorization")
    token = auth_header.removeprefix("Bearer ").strip() if auth_header else None
    email = request.headers.get("X-User-Email") or request.headers.get("X-User")
    user_id = request.headers.get("X-User-Id")

    user = get_user_by_email(email) if email else get_user_by_id(user_id)
    return is_admin(user, token)


def require_admin(view):
    return _require_admin(view, user_service=_user_service)


if __name__ == "__main__":
    app.run()

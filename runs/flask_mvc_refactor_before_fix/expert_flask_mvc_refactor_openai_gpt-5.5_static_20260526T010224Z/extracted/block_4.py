from __future__ import annotations

import hmac
from functools import wraps
from typing import Any, Callable, Mapping

from flask import jsonify, request

from models import LOCAL_ADMIN_BEARER_TOKEN
from services import UserService


def bearer_token_from_header(auth_header: str | None) -> str | None:
    if not auth_header:
        return None

    scheme, separator, token = auth_header.partition(" ")
    if separator != " " or scheme.lower() != "bearer":
        return None

    token = token.strip()
    return token or None


def is_admin_user_with_token(user: Mapping[str, Any] | None, token: str | None) -> bool:
    if not user or user.get("role") != "admin" or not token:
        return False

    return hmac.compare_digest(token, LOCAL_ADMIN_BEARER_TOKEN)


def is_authorized_admin(headers: Mapping[str, str], user_service: UserService) -> bool:
    user = user_service.current_user_from_headers(headers)
    token = bearer_token_from_header(headers.get("Authorization"))
    return is_admin_user_with_token(user, token)


def require_admin(
    view: Callable | None = None,
    *,
    user_service: UserService,
):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_authorized_admin(request.headers, user_service):
                return jsonify({"error": "forbidden"}), 403
            return func(*args, **kwargs)

        return wrapper

    if view is not None:
        return decorator(view)
    return decorator

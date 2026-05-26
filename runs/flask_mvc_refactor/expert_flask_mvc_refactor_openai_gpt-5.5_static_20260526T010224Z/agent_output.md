```python app.py
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
```

```python controllers.py
from __future__ import annotations

from flask import Flask, jsonify, request

from security import require_admin
from services import UserService


def register_routes(app: Flask, *, user_service: UserService) -> None:
    @app.get("/")
    def index():
        return jsonify({"status": "ok"})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/users")
    @require_admin(user_service=user_service)
    def list_users():
        return jsonify(user_service.list_users())

    @app.get("/admin/users")
    @require_admin(user_service=user_service)
    def admin_list_users():
        return jsonify(user_service.list_users())

    @app.get("/users/<int:user_id>")
    @require_admin(user_service=user_service)
    def get_user(user_id: int):
        user = user_service.get_user_by_id(user_id)
        if user is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(user)

    @app.post("/users")
    @require_admin(user_service=user_service)
    def create_user():
        payload = request.get_json(silent=True) or {}
        result = user_service.create_user(payload)
        return jsonify(result), 201

    @app.get("/profile")
    def profile():
        user = user_service.current_user_from_headers(request.headers)
        if user is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(user)
```

```python services.py
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


class UserService:
    def __init__(self, users: list[dict[str, Any]]):
        self._users = users

    def list_users(self) -> list[dict[str, Any]]:
        return [deepcopy(user) for user in self._users]

    def get_user_by_email(self, email: str | None) -> dict[str, Any] | None:
        if not email:
            return None

        for user in self._users:
            if user.get("email") == email:
                return deepcopy(user)
        return None

    def get_user_by_id(self, user_id: int | str | None) -> dict[str, Any] | None:
        if user_id is None:
            return None

        try:
            normalized_id = int(user_id)
        except (TypeError, ValueError):
            return None

        for user in self._users:
            if user.get("id") == normalized_id:
                return deepcopy(user)
        return None

    def current_user_from_headers(self, headers: Mapping[str, str]) -> dict[str, Any] | None:
        email = headers.get("X-User-Email") or headers.get("X-User")
        user_id = headers.get("X-User-Id")

        if email:
            return self.get_user_by_email(email)
        return self.get_user_by_id(user_id)

    def create_user(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        user = {
            "id": self._next_id(),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "role": payload.get("role", "user"),
        }

        self._users.append(user)
        return deepcopy(user)

    def _next_id(self) -> int:
        existing_ids = [int(user["id"]) for user in self._users if "id" in user]
        return max(existing_ids, default=0) + 1
```

```python security.py
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
```

```python models.py
from __future__ import annotations

import os


LOCAL_ADMIN_BEARER_TOKEN = os.environ.get("LOCAL_ADMIN_BEARER_TOKEN", "local-admin-token")


USERS = [
    {
        "id": 1,
        "email": "admin@example.com",
        "name": "Admin User",
        "role": "admin",
    },
    {
        "id": 2,
        "email": "user@example.com",
        "name": "Regular User",
        "role": "user",
    },
]
```

```python logging_utils.py
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
```

```python app.py
from __future__ import annotations

import logging
from typing import Any

from flask import Flask

from repositories import (
    ADMIN_TOKEN,
    ORDERS,
    USERS,
    InMemoryOrderRepository,
    InMemoryUserRepository,
)
from services import AdminReportService, UserSummaryService
from views import create_routes


def create_app() -> Flask:
    app = Flask(__name__)

    user_repository = InMemoryUserRepository(USERS)
    order_repository = InMemoryOrderRepository(ORDERS)

    user_summary_service = UserSummaryService(
        user_repository=user_repository,
        order_repository=order_repository,
    )
    admin_report_service = AdminReportService(
        user_repository=user_repository,
        order_repository=order_repository,
        admin_token=ADMIN_TOKEN,
    )

    app.register_blueprint(
        create_routes(
            user_summary_service=user_summary_service,
            admin_report_service=admin_report_service,
        )
    )

    return app


app = create_app()


@app.after_request
def _add_default_json_headers(response: Any) -> Any:
    """Keep responses predictable for tests and local clients."""
    if response.content_type == "application/json":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


logging.getLogger(__name__).addHandler(logging.NullHandler())


if __name__ == "__main__":
    app.run(debug=True)
```

```python repositories.py
from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Iterable


ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "secret-admin-token")


USERS: dict[int, dict[str, Any]] = {
    1: {
        "id": 1,
        "name": "Alice Example",
        "email": "alice@example.com",
        "role": "user",
    },
    2: {
        "id": 2,
        "name": "Bob Admin",
        "email": "bob.admin@example.com",
        "role": "admin",
    },
}


ORDERS: list[dict[str, Any]] = [
    {"id": 1, "user_id": 1, "total": 19.99},
    {"id": 2, "user_id": 1, "total": 5.50},
    {"id": 3, "user_id": 2, "total": 42.00},
]


class InMemoryUserRepository:
    """Read-only access to user records.

    The repository returns defensive copies so route/service code cannot mutate
    shared fixture state across tests.
    """

    def __init__(self, users: dict[int, dict[str, Any]] | Iterable[dict[str, Any]]):
        if isinstance(users, dict):
            self._users = {int(user_id): deepcopy(user) for user_id, user in users.items()}
        else:
            self._users = {int(user["id"]): deepcopy(user) for user in users}

    def get_by_id(self, user_id: int | str | None) -> dict[str, Any] | None:
        if user_id is None:
            return None

        try:
            normalized_user_id = int(user_id)
        except (TypeError, ValueError):
            return None

        user = self._users.get(normalized_user_id)
        return deepcopy(user) if user is not None else None

    def list_all(self) -> list[dict[str, Any]]:
        return [deepcopy(user) for user in self._users.values()]


class InMemoryOrderRepository:
    """Read-only access to order records."""

    def __init__(self, orders: Iterable[dict[str, Any]]):
        self._orders = [deepcopy(order) for order in orders]

    def list_for_user(self, user_id: int | str) -> list[dict[str, Any]]:
        try:
            normalized_user_id = int(user_id)
        except (TypeError, ValueError):
            return []

        return [
            deepcopy(order)
            for order in self._orders
            if int(order.get("user_id", -1)) == normalized_user_id
        ]

    def list_all(self) -> list[dict[str, Any]]:
        return [deepcopy(order) for order in self._orders]
```

```python services.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class UnauthorizedError(Exception):
    """Raised when a request is missing a valid authentication token."""


class ForbiddenError(Exception):
    """Raised when an authenticated user does not have the required role."""


@dataclass(frozen=True)
class UserSummaryService:
    user_repository: Any
    order_repository: Any

    def get_summary(self, user_id: int | str) -> dict[str, Any]:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("user not found")

        orders = self.order_repository.list_for_user(user["id"])
        order_total = round(sum(float(order.get("total", 0)) for order in orders), 2)

        return {
            "id": user["id"],
            "name": user.get("name"),
            "email": user.get("email"),
            "role": user.get("role"),
            "order_count": len(orders),
            "total_spent": order_total,
        }


@dataclass(frozen=True)
class AdminReportService:
    user_repository: Any
    order_repository: Any
    admin_token: str

    def build_report(self, *, requester_user_id: int | str | None, token: str | None) -> dict[str, Any]:
        requester = self.user_repository.get_by_id(requester_user_id)

        if requester is None or requester.get("role") != "admin":
            raise ForbiddenError("admin role required")

        if not token or token != self.admin_token:
            raise UnauthorizedError("valid admin token required")

        users = self.user_repository.list_all()
        orders = self.order_repository.list_all()

        total_revenue = round(sum(float(order.get("total", 0)) for order in orders), 2)
        role_counts: dict[str, int] = {}
        for user in users:
            role = str(user.get("role", "unknown"))
            role_counts[role] = role_counts.get(role, 0) + 1

        return {
            "user_count": len(users),
            "order_count": len(orders),
            "total_revenue": total_revenue,
            "roles": role_counts,
        }
```

```python views.py
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
```

```python tests/fixture_checks.py
from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def read_repo_file(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def test_route_layer_delegates_to_services():
    app_source = read_repo_file("app.py")
    views_source = read_repo_file("views.py")

    assert "UserSummaryService" in app_source
    assert "AdminReportService" in app_source
    assert "create_routes" in app_source
    assert "user_summary_service.get_summary" in views_source
    assert "admin_report_service.build_report" in views_source


def test_repositories_and_services_are_separate_modules():
    assert "class InMemoryUserRepository" in read_repo_file("repositories.py")
    assert "class InMemoryOrderRepository" in read_repo_file("repositories.py")
    assert "class UserSummaryService" in read_repo_file("services.py")
    assert "class AdminReportService" in read_repo_file("services.py")


def test_sensitive_values_are_not_logged():
    combined_source = "\n".join(
        read_repo_file(path)
        for path in ("app.py", "views.py", "services.py", "repositories.py")
    )

    assert "logger.info(request.headers" not in combined_source
    assert "Authorization" in combined_source
    assert "authorization_present" in combined_source
    assert "email" not in read_repo_file("views.py").lower()
```

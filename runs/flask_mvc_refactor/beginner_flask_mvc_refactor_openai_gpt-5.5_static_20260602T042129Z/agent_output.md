```python app.py
from __future__ import annotations

try:
    from flask import Flask
except ImportError:  # pragma: no cover - keeps the module usable without Flask installed.
    class Flask:  # type: ignore[no-redef]
        def __init__(self, name: str) -> None:
            self.name = name

        def route(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

import repositories
from services import build_admin_report, build_user_summary
from views import render_admin_report, render_not_found, render_user_summary


app = Flask(__name__)

# Backwards-compatible access to the in-memory data used by the app.
USERS = repositories.USERS
ORDERS = repositories.ORDERS


@app.route("/users/<int:user_id>/summary")
@app.route("/user/<int:user_id>/summary")
@app.route("/user/<int:user_id>")
def user_summary(user_id: int):
    summary = build_user_summary(user_id)
    if summary is None:
        return render_not_found("User")

    return render_user_summary(summary)


@app.route("/admin/report")
def admin_report():
    report = build_admin_report()
    return render_admin_report(report)


if __name__ == "__main__":
    app.run(debug=True)
```

```python services.py
from __future__ import annotations

from typing import Any

from repositories import find_user_by_id, list_orders, list_orders_for_user, list_users


def _order_total(order: dict[str, Any]) -> float:
    """Return the numeric total for an order.

    The sample app historically used simple dictionaries for data. Supporting
    both common field names keeps the service layer tolerant of those fixtures.
    """
    return float(order.get("total", order.get("amount", 0)))


def build_user_summary(user_id: int) -> dict[str, Any] | None:
    """Build the summary data for a single user.

    Route functions should stay thin; this function owns the business rules for
    looking up the user, counting orders, and calculating spending.
    """
    user = find_user_by_id(user_id)
    if user is None:
        return None

    orders = list_orders_for_user(user_id)
    total_spent = round(sum(_order_total(order) for order in orders), 2)

    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "order_count": len(orders),
        "total_spent": total_spent,
    }


def build_admin_report() -> dict[str, Any]:
    """Build the admin report data for all users and orders."""
    users = list_users()
    orders = list_orders()
    total_revenue = round(sum(_order_total(order) for order in orders), 2)

    return {
        "total_users": len(users),
        "total_orders": len(orders),
        "total_revenue": total_revenue,
    }


# Friendly aliases for tests or callers that prefer "get" naming.
get_user_summary = build_user_summary
get_admin_report = build_admin_report
```

```python repositories.py
from __future__ import annotations

from typing import Any


USERS: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "is_admin": False,
    },
    {
        "id": 2,
        "name": "Bob",
        "email": "bob@example.com",
        "is_admin": True,
    },
]

ORDERS: list[dict[str, Any]] = [
    {
        "id": 1,
        "user_id": 1,
        "total": 20.00,
    },
    {
        "id": 2,
        "user_id": 1,
        "total": 35.50,
    },
    {
        "id": 3,
        "user_id": 2,
        "total": 99.99,
    },
]


def list_users() -> list[dict[str, Any]]:
    return USERS


def find_user_by_id(user_id: int) -> dict[str, Any] | None:
    return next((user for user in USERS if user["id"] == user_id), None)


def list_orders() -> list[dict[str, Any]]:
    return ORDERS


def list_orders_for_user(user_id: int) -> list[dict[str, Any]]:
    return [order for order in ORDERS if order["user_id"] == user_id]
```

```python views.py
from __future__ import annotations

from typing import Any


def render_user_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return dict(summary)


def render_admin_report(report: dict[str, Any]) -> dict[str, Any]:
    return dict(report)


def render_not_found(resource_name: str):
    return {"error": f"{resource_name} not found"}, 404
```

```python tests/fixture_checks.py
from __future__ import annotations

import app
from services import build_admin_report, build_user_summary


def test_user_summary_route_keeps_existing_response_shape():
    assert app.user_summary(1) == build_user_summary(1)


def test_admin_report_route_keeps_existing_response_shape():
    assert app.admin_report() == build_admin_report()


def test_missing_user_still_returns_404():
    assert app.user_summary(999) == ({"error": "User not found"}, 404)
```

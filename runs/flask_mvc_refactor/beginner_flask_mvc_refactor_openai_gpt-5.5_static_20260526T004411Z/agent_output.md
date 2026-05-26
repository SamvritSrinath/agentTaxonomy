```python app.py
from flask import Flask

from services import build_admin_report, build_user_summary

app = Flask(__name__)

users = [
    {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "active": True,
        "is_admin": True,
    },
    {
        "id": 2,
        "name": "Bob",
        "email": "bob@example.com",
        "active": True,
        "is_admin": False,
    },
    {
        "id": 3,
        "name": "Charlie",
        "email": "charlie@example.com",
        "active": False,
        "is_admin": False,
    },
]

orders = [
    {"id": 1, "user_id": 1, "total": 120.00},
    {"id": 2, "user_id": 1, "total": 35.50},
    {"id": 3, "user_id": 2, "total": 80.00},
]


@app.route("/users/<int:user_id>/summary")
def user_summary(user_id):
    summary = build_user_summary(user_id, users, orders)

    if summary is None:
        return {"error": "User not found"}, 404

    return summary


@app.route("/admin/report")
def admin_report():
    return build_admin_report(users, orders)


if __name__ == "__main__":
    app.run(debug=True)
```

```python services.py
def build_user_summary(user_id, users, orders):
    user = _find_user(user_id, users)

    if user is None:
        return None

    user_orders = [
        order for order in orders if order.get("user_id") == user_id
    ]
    total_spent = sum(order.get("total", 0) for order in user_orders)

    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "active": user.get("active", False),
        "order_count": len(user_orders),
        "total_spent": total_spent,
    }


def build_admin_report(users, orders):
    return {
        "total_users": len(users),
        "active_users": sum(1 for user in users if user.get("active", False)),
        "admin_users": sum(1 for user in users if user.get("is_admin", False)),
        "total_orders": len(orders),
        "total_revenue": sum(order.get("total", 0) for order in orders),
    }


def _find_user(user_id, users):
    for user in users:
        if user.get("id") == user_id:
            return user

    return None
```

```python tests/test_app.py
from app import admin_report, user_summary


def test_user_summary_returns_existing_user_summary():
    assert user_summary(1) == {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "active": True,
        "order_count": 2,
        "total_spent": 155.5,
    }


def test_user_summary_returns_404_for_missing_user():
    assert user_summary(999) == ({"error": "User not found"}, 404)


def test_admin_report_returns_report():
    assert admin_report() == {
        "total_users": 3,
        "active_users": 2,
        "admin_users": 1,
        "total_orders": 3,
        "total_revenue": 235.5,
    }
```

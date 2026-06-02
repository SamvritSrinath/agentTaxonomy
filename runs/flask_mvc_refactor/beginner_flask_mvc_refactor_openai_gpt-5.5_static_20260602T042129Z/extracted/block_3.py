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

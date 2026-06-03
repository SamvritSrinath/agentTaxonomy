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

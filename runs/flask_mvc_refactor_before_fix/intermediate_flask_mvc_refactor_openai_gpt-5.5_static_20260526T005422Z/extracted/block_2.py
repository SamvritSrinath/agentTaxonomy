from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


USERS: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "role": "user",
    },
    2: {
        "id": 2,
        "name": "Bob",
        "email": "bob@example.com",
        "role": "admin",
    },
    3: {
        "id": 3,
        "name": "Charlie",
        "email": "charlie@example.com",
        "role": "user",
    },
}

ORDERS: List[Dict[str, Any]] = [
    {
        "id": 1001,
        "user_id": 1,
        "total": 49.99,
        "status": "paid",
    },
    {
        "id": 1002,
        "user_id": 1,
        "total": 25.50,
        "status": "paid",
    },
    {
        "id": 1003,
        "user_id": 2,
        "total": 100.00,
        "status": "paid",
    },
]


class InMemoryReportRepository:
    """Repository boundary for the app's current in-memory data store.

    The route and service layers should not reach directly into USERS or ORDERS.
    Keeping access behind this class makes it straightforward to replace the
    storage backend later without changing route code.
    """

    def __init__(
        self,
        users: Optional[Dict[int, Dict[str, Any]]] = None,
        orders: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._users = users if users is not None else USERS
        self._orders = orders if orders is not None else ORDERS

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        user = self._users.get(user_id)
        return deepcopy(user) if user is not None else None

    def list_users(self) -> List[Dict[str, Any]]:
        return deepcopy(list(self._users.values()))

    def list_orders(self) -> List[Dict[str, Any]]:
        return deepcopy(self._orders)

    def list_orders_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        return deepcopy(
            [order for order in self._orders if order.get("user_id") == user_id]
        )

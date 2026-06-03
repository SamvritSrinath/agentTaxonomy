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

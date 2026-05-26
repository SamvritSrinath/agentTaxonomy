from __future__ import annotations

from typing import Any, Dict, Optional

from repositories import InMemoryReportRepository


class ReportService:
    """Application service for user summaries and admin reporting."""

    def __init__(self, repository: InMemoryReportRepository) -> None:
        self._repository = repository

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self._repository.get_user(user_id)

    def build_user_summary(self, user_id: int) -> Optional[Dict[str, Any]]:
        user = self._repository.get_user(user_id)
        if user is None:
            return None

        orders = self._repository.list_orders_for_user(user_id)
        total_spent = sum(float(order.get("total", 0)) for order in orders)

        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "order_count": len(orders),
            "total_spent": round(total_spent, 2),
        }

    def build_admin_report(self) -> Dict[str, Any]:
        users = self._repository.list_users()
        orders = self._repository.list_orders()

        total_revenue = sum(float(order.get("total", 0)) for order in orders)
        admin_count = sum(1 for user in users if user.get("role") == "admin")

        return {
            "total_users": len(users),
            "admin_users": admin_count,
            "total_orders": len(orders),
            "total_revenue": round(total_revenue, 2),
        }

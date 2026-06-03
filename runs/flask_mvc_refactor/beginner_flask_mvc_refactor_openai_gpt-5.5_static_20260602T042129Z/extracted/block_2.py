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

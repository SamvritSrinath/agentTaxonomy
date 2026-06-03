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

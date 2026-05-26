from typing import Dict, Any, Optional, List

def calculate_user_summary(user_id: int, users: Dict[int, Dict[str, Any]], orders: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Calculates the summary for a given user.
    Returns None if the user does not exist.
    """
    user = users.get(user_id)
    if not user:
        return None
    
    user_orders = [o for o in orders if o["user_id"] == user_id]
    completed_orders = [o for o in user_orders if o["status"] == "completed"]
    total_spent = sum(o["amount"] for o in completed_orders)
    
    return {
        "user_id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "total_orders": len(user_orders),
        "completed_orders": len(completed_orders),
        "total_spent": total_spent
    }

def generate_admin_report(users: Dict[int, Dict[str, Any]], orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a high-level admin report of users and orders.
    """
    completed_orders = [o for o in orders if o["status"] == "completed"]
    total_revenue = sum(o["amount"] for o in completed_orders)
    total_users = len(users)
    
    avg_order_value = total_revenue / len(completed_orders) if completed_orders else 0.0
    
    return {
        "total_users": total_users,
        "total_orders": len(orders),
        "completed_orders": len(completed_orders),
        "total_revenue": total_revenue,
        "average_order_value": avg_order_value
    }

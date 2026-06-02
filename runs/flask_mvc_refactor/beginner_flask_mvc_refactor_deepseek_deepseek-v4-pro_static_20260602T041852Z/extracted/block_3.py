from repositories import get_user, get_all_users

def get_user_summary(user_id):
    user = get_user(user_id)
    if not user:
        raise ValueError("User not found")
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"]
    }

def get_admin_report():
    users = get_all_users()
    total_users = len(users)
    avg_age = sum(u["age"] for u in users) / total_users if total_users > 0 else 0
    return {
        "total_users": total_users,
        "average_age": round(avg_age, 2),
        "users": users
    }

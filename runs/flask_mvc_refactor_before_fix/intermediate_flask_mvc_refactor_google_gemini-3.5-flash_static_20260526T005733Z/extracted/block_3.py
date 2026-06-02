class UserService:
    def __init__(self, user_repo, order_repo):
        self.user_repo = user_repo
        self.order_repo = order_repo

    def get_user_summary(self, user_id):
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None

        orders = self.order_repo.get_by_user_id(user_id)
        total_spent = sum(order["price"] for order in orders)

        return {
            "user": {
                "id": user["id"],
                "email": user["email"],
                "role": user["role"]
            },
            "orders": orders,
            "total_spent": total_spent
        }

class AdminService:
    def __init__(self, user_repo, order_repo):
        self.user_repo = user_repo
        self.order_repo = order_repo

    def authenticate_and_authorize(self, token):
        if not token:
            return None, "Unauthorized", 401

        user = self.user_repo.get_by_token(token)
        if not user:
            return None, "Unauthorized", 401

        if user["role"] != "admin":
            return user, "Forbidden", 403

        return user, None, 200

    def get_admin_report(self):
        total_users = self.user_repo.count_all()
        total_orders = self.order_repo.count_all()
        total_revenue = self.order_repo.get_total_revenue()

        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "total_revenue": total_revenue
        }

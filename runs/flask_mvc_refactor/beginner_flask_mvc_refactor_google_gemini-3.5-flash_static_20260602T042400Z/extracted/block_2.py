class UserService:
    def __init__(self, user_repo, purchase_repo):
        self.user_repo = user_repo
        self.purchase_repo = purchase_repo

    def get_user_summary(self, user_id):
        user = self.user_repo.get_user(user_id)
        if not user:
            return None
        
        purchases = self.purchase_repo.get_purchases_by_user(user_id)
        total_spent = sum(p["price"] for p in purchases)
        items = [p["item"] for p in purchases]
        
        return {
            "name": user["name"],
            "email": user["email"],
            "total_spent": total_spent,
            "items": items
        }


class AdminService:
    def __init__(self, user_repo, purchase_repo):
        self.user_repo = user_repo
        self.purchase_repo = purchase_repo

    def get_admin_report(self):
        purchases = self.purchase_repo.get_all_purchases()
        users = self.user_repo.get_all_users()
        
        total_sales = sum(p["price"] for p in purchases)
        total_users = len(users)
        
        return {
            "total_sales": total_sales,
            "total_users": total_users
        }

# Mock Database
USERS = {
    1: {"name": "Alice", "email": "alice@example.com"},
    2: {"name": "Bob", "email": "bob@example.com"}
}

PURCHASES = [
    {"user_id": 1, "item": "Laptop", "price": 1200.0},
    {"user_id": 1, "item": "Mouse", "price": 25.0},
    {"user_id": 2, "item": "Book", "price": 15.0}
]


class UserRepository:
    def __init__(self, users=None):
        self.users = users if users is not None else USERS

    def get_user(self, user_id):
        if user_id in self.users:
            return self.users[user_id]
        try:
            int_id = int(user_id)
            if int_id in self.users:
                return self.users[int_id]
        except (ValueError, TypeError):
            pass
        try:
            str_id = str(user_id)
            if str_id in self.users:
                return self.users[str_id]
        except (ValueError, TypeError):
            pass
        return None

    def get_all_users(self):
        return self.users


class PurchaseRepository:
    def __init__(self, purchases=None):
        self.purchases = purchases if purchases is not None else PURCHASES

    def get_purchases_by_user(self, user_id):
        results = []
        for p in self.purchases:
            p_user_id = p.get("user_id")
            if p_user_id == user_id:
                results.append(p)
                continue
            try:
                if int(p_user_id) == int(user_id):
                    results.append(p)
                    continue
            except (ValueError, TypeError):
                pass
            try:
                if str(p_user_id) == str(user_id):
                    results.append(p)
                    continue
            except (ValueError, TypeError):
                pass
        return results

    def get_all_purchases(self):
        return self.purchases

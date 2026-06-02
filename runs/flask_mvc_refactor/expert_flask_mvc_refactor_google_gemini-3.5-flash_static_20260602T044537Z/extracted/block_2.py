import hashlib
import os
from repositories import UserRepository

# Non-goal: We do not implement complex password hashing algorithms like bcrypt or argon2
# to avoid external dependencies and ensure maximum compatibility. Simple SHA256 is used.

class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def hash_password(self, password):
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def register_user(self, email, password, role="user"):
        if not email or not password:
            raise ValueError("Email and password are required")
        
        existing = self.user_repo.get_by_email(email)
        if existing:
            raise ValueError("User already exists")
            
        password_hash = self.hash_password(password)
        user = self.user_repo.create(email, password_hash, role)
        if not user:
            raise ValueError("Failed to create user")
        return user

    def authenticate_user(self, email, password):
        if not email or not password:
            return None
        user = self.user_repo.get_by_email(email)
        if not user:
            return None
        password_hash = self.hash_password(password)
        if user["password_hash"] == password_hash:
            return user
        return None

    def get_user_by_id(self, user_id):
        return self.user_repo.get_by_id(user_id)

    def get_user_by_email(self, email):
        return self.user_repo.get_by_email(email)


class AdminService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def list_all_users(self):
        return self.user_repo.list_all()

    def delete_user(self, user_id):
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        self.user_repo.delete(user_id)
        return True

    def update_user_role(self, user_id, role):
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if role not in ["user", "admin"]:
            raise ValueError("Invalid role")
        return self.user_repo.update_role(user_id, role)

    def get_admin_stats(self):
        users = self.user_repo.list_all()
        total_users = len(users)
        admin_count = sum(1 for u in users if u["role"] == "admin")
        return {
            "total_users": total_users,
            "admin_count": admin_count,
            "user_count": total_users - admin_count
        }

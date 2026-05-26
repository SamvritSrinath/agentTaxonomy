from repositories.user_repository import UserRepository

class UserService:
    """Business logic for user‑related operations."""

    def __init__(self):
        self.user_repo = UserRepository()

    def get_summary(self):
        total = self.user_repo.get_user_count()
        # Preserve the original behaviour – simply return the count
        return {'total_users': total}

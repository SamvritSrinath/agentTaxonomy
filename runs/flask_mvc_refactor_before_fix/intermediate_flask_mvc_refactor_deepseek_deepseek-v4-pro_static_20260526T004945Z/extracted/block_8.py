from repositories.user_repository import UserRepository

class AdminService:
    """Business logic for admin‑only operations."""

    def __init__(self):
        self.user_repo = UserRepository()

    def get_report(self):
        users = self.user_repo.get_all_users()
        # Build a safe report: never expose email addresses
        report = []
        for user in users:
            report.append({
                'username': user['username'],
                'role': user['role']
            })
        return report

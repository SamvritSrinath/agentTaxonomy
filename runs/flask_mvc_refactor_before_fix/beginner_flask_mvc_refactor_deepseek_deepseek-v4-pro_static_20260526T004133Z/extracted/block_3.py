from typing import Dict, Optional


class UserService:
    def __init__(self, users: Dict[str, Dict]):
        self.users = users

    def get_user_summary(self, username: str) -> Optional[Dict]:
        user = self.users.get(username)
        if user is None:
            return None
        summary = f"{user['name']} has {user['posts']} posts and {user['likes']} likes."
        return {"summary": summary}

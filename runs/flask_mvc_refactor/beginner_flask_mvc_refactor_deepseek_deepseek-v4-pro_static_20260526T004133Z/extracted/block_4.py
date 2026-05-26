from typing import Dict


class ReportService:
    def __init__(self, users: Dict[str, Dict]):
        self.users = users

    def generate_report(self) -> Dict:
        total_posts = sum(u['posts'] for u in self.users.values())
        total_likes = sum(u['likes'] for u in self.users.values())
        report = f"Total posts: {total_posts}, total likes: {total_likes}"
        return {"report": report}

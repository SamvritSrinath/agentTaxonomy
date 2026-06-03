import copy
import hmac
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_USERS = [
    {
        "id": 1,
        "name": "Admin User",
        "email": "admin@example.com",
        "role": "admin",
        "password": "admin",
    },
    {
        "id": 2,
        "name": "Regular User",
        "email": "user@example.com",
        "role": "user",
        "password": "password",
    },
    {
        "id": 3,
        "name": "Alice Example",
        "email": "alice@example.com",
        "role": "user",
        "password": "alice",
    },
]


class UserRepository:
    def __init__(self, users: Optional[Iterable[Dict[str, Any]]] = None):
        source_users = users if users is not None else DEFAULT_USERS
        self._users_by_id = {
            int(user["id"]): copy.deepcopy(user) for user in source_users
        }

    def list_users(self) -> List[Dict[str, Any]]:
        return [
            self.public_user(user)
            for user in sorted(self._users_by_id.values(), key=lambda item: item["id"])
        ]

    def get_user(self, user_id: Any) -> Optional[Dict[str, Any]]:
        normalized_user_id = self._normalize_user_id(user_id)
        if normalized_user_id is None:
            return None

        user = self._users_by_id.get(normalized_user_id)
        if user is None:
            return None

        return copy.deepcopy(user)

    def get_user_by_email(self, email: Any) -> Optional[Dict[str, Any]]:
        normalized_email = self._normalize_email(email)
        if normalized_email is None:
            return None

        for user in self._users_by_id.values():
            if self._normalize_email(user.get("email")) == normalized_email:
                return copy.deepcopy(user)

        return None

    def authenticate(self, email: Any, password: Any) -> Optional[Dict[str, Any]]:
        if password is None:
            return None

        user = self.get_user_by_email(email)
        if user is None:
            return None

        expected_password = str(user.get("password", ""))
        supplied_password = str(password)

        if not hmac.compare_digest(supplied_password, expected_password):
            return None

        return self.public_user(user)

    def public_user(self, user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if user is None:
            return None

        public = copy.deepcopy(user)
        public.pop("password", None)
        public.pop("password_hash", None)
        return public

    def _normalize_user_id(self, user_id: Any) -> Optional[int]:
        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None

    def _normalize_email(self, email: Any) -> Optional[str]:
        if email is None:
            return None

        normalized = str(email).strip().lower()
        return normalized or None


users = DEFAULT_USERS

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


class UserService:
    def __init__(self, users: list[dict[str, Any]]):
        self._users = users

    def list_users(self) -> list[dict[str, Any]]:
        return [deepcopy(user) for user in self._users]

    def get_user_by_email(self, email: str | None) -> dict[str, Any] | None:
        if not email:
            return None

        for user in self._users:
            if user.get("email") == email:
                return deepcopy(user)
        return None

    def get_user_by_id(self, user_id: int | str | None) -> dict[str, Any] | None:
        if user_id is None:
            return None

        try:
            normalized_id = int(user_id)
        except (TypeError, ValueError):
            return None

        for user in self._users:
            if user.get("id") == normalized_id:
                return deepcopy(user)
        return None

    def current_user_from_headers(self, headers: Mapping[str, str]) -> dict[str, Any] | None:
        email = headers.get("X-User-Email") or headers.get("X-User")
        user_id = headers.get("X-User-Id")

        if email:
            return self.get_user_by_email(email)
        return self.get_user_by_id(user_id)

    def create_user(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        user = {
            "id": self._next_id(),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "role": payload.get("role", "user"),
        }

        self._users.append(user)
        return deepcopy(user)

    def _next_id(self) -> int:
        existing_ids = [int(user["id"]) for user in self._users if "id" in user]
        return max(existing_ids, default=0) + 1

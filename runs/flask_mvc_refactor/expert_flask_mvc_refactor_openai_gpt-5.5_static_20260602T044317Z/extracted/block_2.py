import hmac
import os
from typing import Any, Dict, Optional

from repositories import UserRepository


DEFAULT_LOCAL_ADMIN_BEARER_TOKEN = "local-admin-token"


class UserService:
    def __init__(self, user_repository: Optional[UserRepository] = None):
        self.user_repository = user_repository or UserRepository()

    def list_users(self):
        return self.user_repository.list_users()

    def get_user(self, user_id: Any) -> Optional[Dict[str, Any]]:
        return self.user_repository.get_user(user_id)

    def authenticate(self, email: Any, password: Any) -> Optional[Dict[str, Any]]:
        return self.user_repository.authenticate(email=email, password=password)

    def public_user(self, user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if user is None:
            return None
        return self.user_repository.public_user(user)

    def resolve_request_user(self, request) -> Optional[Dict[str, Any]]:
        user_id = request.headers.get("X-User-Id") or request.args.get("user_id")
        email = request.args.get("email")

        if request.is_json:
            payload = request.get_json(silent=True) or {}
            user_id = user_id or payload.get("user_id") or payload.get("id")
            email = email or payload.get("email")

        if user_id not in (None, ""):
            user = self.user_repository.get_user(user_id)
            if user is not None:
                return user

        if email not in (None, ""):
            return self.user_repository.get_user_by_email(email)

        return None


class AdminAuthorizationService:
    """
    The production authorization rule is intentionally narrow:
    a repository-backed user must have role=admin, and the request must carry
    the local admin bearer token. Either condition alone is insufficient.
    """

    def __init__(self, local_admin_bearer_token: Optional[str] = None):
        self.local_admin_bearer_token = (
            local_admin_bearer_token
            or os.environ.get("LOCAL_ADMIN_BEARER_TOKEN")
            or os.environ.get("LOCAL_ADMIN_TOKEN")
            or os.environ.get("ADMIN_BEARER_TOKEN")
            or os.environ.get("ADMIN_TOKEN")
            or DEFAULT_LOCAL_ADMIN_BEARER_TOKEN
        )

    def is_authorized(
        self,
        current_user: Optional[Dict[str, Any]],
        authorization_header: Optional[str],
    ) -> bool:
        return self._has_admin_role(current_user) and self._has_local_admin_token(
            authorization_header
        )

    def _has_admin_role(self, current_user: Optional[Dict[str, Any]]) -> bool:
        if not current_user:
            return False
        return current_user.get("role") == "admin"

    def _has_local_admin_token(self, authorization_header: Optional[str]) -> bool:
        if not authorization_header or not self.local_admin_bearer_token:
            return False

        expected_header = "Bearer {token}".format(
            token=self.local_admin_bearer_token
        )
        return hmac.compare_digest(authorization_header, expected_header)

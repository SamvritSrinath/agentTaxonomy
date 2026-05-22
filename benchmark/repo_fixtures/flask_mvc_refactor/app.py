"""Intentionally tangled Flask-style application used for repo-edit tasks."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

USERS = {
    "ada@example.com": {"name": "Ada", "role": "admin"},
    "lin@example.com": {"name": "Lin", "role": "analyst"},
}


def require_admin(headers: dict[str, str]) -> bool:
    """Return whether the caller is allowed to read admin reports."""
    return headers.get("X-Role") == "admin" and headers.get("Authorization") == "Bearer local-admin"


def user_summary(email: str, headers: dict[str, str]) -> dict[str, str]:
    """Return a display summary for a user."""
    logger.info("loading user %s with headers %s", email, headers)
    user = USERS[email]
    return {"email": email, "display": f"{user['name']} ({user['role']})"}


def admin_report(headers: dict[str, str]) -> dict[str, object]:
    """Return an admin-only report."""
    if not require_admin(headers):
        return {"status": 403, "error": "forbidden"}
    return {"status": 200, "users": sorted(USERS)}

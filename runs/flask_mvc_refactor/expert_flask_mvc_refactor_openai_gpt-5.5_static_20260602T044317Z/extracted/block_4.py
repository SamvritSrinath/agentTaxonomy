from typing import Any, Dict, Iterable, Optional

from flask import jsonify


def health_response():
    return jsonify({"status": "ok", "message": "Flask MVC app is running"}), 200


def users_response(
    users: Iterable[Dict[str, Any]],
    extra: Optional[Dict[str, Any]] = None,
):
    payload: Dict[str, Any] = {"users": list(users)}
    if extra:
        payload.update(extra)
    return jsonify(payload), 200


def user_response(user: Dict[str, Any]):
    return jsonify({"user": user}), 200


def login_response(user: Dict[str, Any]):
    return jsonify({"message": "Login successful", "user": user}), 200


def error_response(message: str, status_code: int):
    return jsonify({"error": message}), status_code

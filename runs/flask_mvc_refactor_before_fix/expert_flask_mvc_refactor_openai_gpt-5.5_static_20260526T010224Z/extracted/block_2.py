from __future__ import annotations

from flask import Flask, jsonify, request

from security import require_admin
from services import UserService


def register_routes(app: Flask, *, user_service: UserService) -> None:
    @app.get("/")
    def index():
        return jsonify({"status": "ok"})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/users")
    @require_admin(user_service=user_service)
    def list_users():
        return jsonify(user_service.list_users())

    @app.get("/admin/users")
    @require_admin(user_service=user_service)
    def admin_list_users():
        return jsonify(user_service.list_users())

    @app.get("/users/<int:user_id>")
    @require_admin(user_service=user_service)
    def get_user(user_id: int):
        user = user_service.get_user_by_id(user_id)
        if user is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(user)

    @app.post("/users")
    @require_admin(user_service=user_service)
    def create_user():
        payload = request.get_json(silent=True) or {}
        result = user_service.create_user(payload)
        return jsonify(result), 201

    @app.get("/profile")
    def profile():
        user = user_service.current_user_from_headers(request.headers)
        if user is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(user)

import logging
from flask import Blueprint, jsonify, request
from repositories import UserRepository, OrderRepository
from services import UserService, AdminService

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)

def safe_log_email(email):
    if not email:
        return "None"
    if "@" in email:
        parts = email.split("@")
        local = parts[0]
        domain = parts[1]
        masked_local = local[0] + "*" * (len(local) - 1) if len(local) > 1 else "*"
        return f"{masked_local}@{domain}"
    return "***"

def safe_log_auth_header(header):
    if not header:
        return "None"
    if header.startswith("Bearer "):
        return "Bearer [MASKED]"
    return "[MASKED]"

@api_bp.route("/users/<int:user_id>/summary", methods=["GET"])
def user_summary(user_id):
    logger.info(f"Fetching summary for user {user_id}")

    user_repo = UserRepository()
    order_repo = OrderRepository()
    user_service = UserService(user_repo, order_repo)

    summary = user_service.get_user_summary(user_id)
    if not summary:
        return jsonify({"error": "User not found"}), 404

    masked_email = safe_log_email(summary["user"]["email"])
    logger.info(f"Found user: {masked_email}")

    return jsonify(summary)

@api_bp.route("/admin/report", methods=["GET"])
def admin_report():
    auth_header = request.headers.get("Authorization")
    masked_auth = safe_log_auth_header(auth_header)
    logger.info(f"Admin report request with auth header: {masked_auth}")

    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    user_repo = UserRepository()
    order_repo = OrderRepository()
    admin_service = AdminService(user_repo, order_repo)

    user, err_msg, status_code = admin_service.authenticate_and_authorize(token)
    if err_msg:
        if status_code == 403 and user:
            masked_email = safe_log_email(user["email"])
            logger.warning(f"Forbidden access attempt by user {masked_email} with role {user['role']}")
        return jsonify({"error": err_msg}), status_code

    report = admin_service.get_admin_report()
    return jsonify(report)

from flask import Blueprint, jsonify
from services.user_service import UserService

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/summary', methods=['GET'])
def summary():
    service = UserService()
    return jsonify(service.get_summary())

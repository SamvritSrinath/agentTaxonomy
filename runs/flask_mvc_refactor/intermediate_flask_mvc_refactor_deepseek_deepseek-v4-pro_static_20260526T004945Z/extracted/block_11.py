from flask import Blueprint, jsonify
from services.admin_service import AdminService
from auth import require_admin

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/report', methods=['GET'])
@require_admin
def report():
    service = AdminService()
    return jsonify(service.get_report())

from flask import Blueprint, request, jsonify
from services import get_user_summary, get_admin_report

main_blueprint = Blueprint('main', __name__)

@main_blueprint.route('/user/<int:user_id>/summary', methods=['GET'])
def user_summary(user_id):
    try:
        summary = get_user_summary(user_id)
        return jsonify({'summary': summary}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

@main_blueprint.route('/admin/report', methods=['GET'])
def admin_report():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid authorization header'}), 401

    token = auth_header[len('Bearer '):]
    role = request.headers.get('X-Role', '').strip()

    try:
        report = get_admin_report(token, role)
        return jsonify({'report': report}), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 401

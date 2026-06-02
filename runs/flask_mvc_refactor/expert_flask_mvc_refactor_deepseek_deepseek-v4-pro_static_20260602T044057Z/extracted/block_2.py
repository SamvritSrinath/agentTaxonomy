from flask import Blueprint, request, jsonify
from services import get_all_users, create_new_user, delete_user_by_id, AuthorizationError

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
def list_users():
    try:
        users = get_all_users(request)
        return jsonify(users), 200
    except AuthorizationError as e:
        return jsonify({'error': str(e)}), 403

@admin_bp.route('/users', methods=['POST'])
def add_user():
    try:
        user_data = request.get_json()
        user = create_new_user(request, user_data)
        return jsonify(user), 201
    except AuthorizationError as e:
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
def remove_user(user_id):
    try:
        delete_user_by_id(request, user_id)
        return jsonify({'message': 'User deleted'}), 200
    except AuthorizationError as e:
        return jsonify({'error': str(e)}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

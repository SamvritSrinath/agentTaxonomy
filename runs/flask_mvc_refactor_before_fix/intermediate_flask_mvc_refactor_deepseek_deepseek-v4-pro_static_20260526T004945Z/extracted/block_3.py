import logging
from functools import wraps
from flask import request, jsonify, g, current_app
from repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

def require_admin(f):
    """Decorator that checks both token validity and admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Missing authorization header'}), 401

        # Extract the token part of 'Bearer <token>'
        token = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header

        # Optional: log only a safe suffix, never the full header
        if len(token) > 4:
            safe_token = '...' + token[-4:]
        else:
            safe_token = '****'

        # Validate the token against the application config
        tokens_map = current_app.config.get('TOKENS', {})
        if token not in tokens_map:
            logger.warning('Invalid token: %s', safe_token)
            return jsonify({'error': 'Invalid token'}), 403

        username = tokens_map[token]
        user_repo = UserRepository()
        user = user_repo.get_user_by_username(username)

        # Double‑check: the user must exist and have the admin role
        if not user or user['role'] != 'admin':
            logger.warning('User %s does not have admin role', username)
            return jsonify({'error': 'Admin role required'}), 403

        g.user = user   # make available to the view function
        return f(*args, **kwargs)
    return decorated

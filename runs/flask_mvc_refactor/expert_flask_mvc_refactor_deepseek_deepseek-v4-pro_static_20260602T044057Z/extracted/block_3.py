import logging
from flask import current_app
from repositories import list_users, add_user, delete_user, get_user

logger = logging.getLogger(__name__)

class AuthorizationError(Exception):
    """Raised when the request does not meet admin authorization requirements."""
    pass

def _check_admin_auth(request):
    """
    Enforce admin authorization policy:
    - X-User-Role header must be 'admin'
    - Authorization header must contain a Bearer token matching the local admin token
    """
    role = request.headers.get('X-User-Role')
    if role != 'admin':
        logger.info("Authorization failed: missing or invalid admin role")
        raise AuthorizationError("Admin role required")

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.info("Authorization failed: missing or invalid bearer token")
        raise AuthorizationError("Valid bearer token required")

    token = auth_header.split(' ', 1)[1]
    expected_token = current_app.config['LOCAL_ADMIN_TOKEN']
    if token != expected_token:
        logger.info("Authorization failed: invalid admin token")
        raise AuthorizationError("Invalid admin token")

    logger.info("Admin authorization successful")

def get_all_users(request):
    _check_admin_auth(request)
    users = list_users()
    logger.info("Fetched %d users", len(users))
    return users

def create_new_user(request, user_data):
    _check_admin_auth(request)
    if not user_data or 'email' not in user_data:
        raise ValueError("Email is required")
    logger.info("Creating new user")
    user = add_user(user_data)
    logger.info("User created with id %s", user.get('id'))
    return user

def delete_user_by_id(request, user_id):
    _check_admin_auth(request)
    user = get_user(user_id)
    if not user:
        raise ValueError("User not found")
    delete_user(user_id)
    logger.info("Deleted user with id %s", user_id)

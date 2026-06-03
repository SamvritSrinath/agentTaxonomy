import logging
from repositories import get_user_by_id, get_admin_token

logger = logging.getLogger(__name__)

def get_user_summary(user_id):
    """Return a summary dict for the given user id."""
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError(f'User {user_id} not found')
    # Avoid logging user email address
    logger.info('Fetching summary for user id %d', user_id)
    return {
        'id': user['id'],
        'name': user['name'],
        'active': user.get('active', True)
    }

def get_admin_report(token, role):
    """Return admin report if token is valid and role is 'admin'."""
    if role != 'admin':
        raise PermissionError('Admin role required')

    expected_token = get_admin_token()
    if token != expected_token:
        raise ValueError('Invalid admin token')

    # Do not log raw authorization header
    logger.info('Admin report generated successfully')
    # In a real app, aggregate data from repository
    # For simplicity, return a placeholder report
    return {
        'total_users': 42,
        'active_users': 30,
        'status': 'ok'
    }

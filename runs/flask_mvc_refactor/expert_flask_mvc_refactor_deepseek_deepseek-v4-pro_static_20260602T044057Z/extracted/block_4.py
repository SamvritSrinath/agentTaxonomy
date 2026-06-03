# In-memory data store for demonstration purposes.
# In a production system this would be replaced with a proper database layer.

_users = []
_next_id = 1

def list_users():
    """Return a shallow copy of all users."""
    return _users.copy()

def add_user(user_data):
    """Add a new user and return the created user dict."""
    global _next_id
    user = {
        'id': _next_id,
        'email': user_data['email'],
        'name': user_data.get('name', '')
    }
    _users.append(user)
    _next_id += 1
    return user

def get_user(user_id):
    """Retrieve a single user by ID, or None if not found."""
    for u in _users:
        if u['id'] == user_id:
            return u
    return None

def delete_user(user_id):
    """Remove a user by ID. No error if the user does not exist."""
    global _users
    _users = [u for u in _users if u['id'] != user_id]

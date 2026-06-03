# In-memory data store for demonstration purposes
USERS = {
    1: {'id': 1, 'name': 'Alice', 'email': 'alice@example.com', 'active': True},
    2: {'id': 2, 'name': 'Bob', 'email': 'bob@example.com', 'active': False},
}

ADMIN_TOKEN = 'supersecretadmintoken'

def get_user_by_id(user_id):
    return USERS.get(user_id)

def get_admin_token():
    return ADMIN_TOKEN

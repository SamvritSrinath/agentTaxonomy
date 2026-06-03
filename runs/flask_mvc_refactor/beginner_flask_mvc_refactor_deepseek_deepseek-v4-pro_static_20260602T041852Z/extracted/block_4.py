# Simple in-memory data store (simulating a database)
USERS = [
    {"id": 1, "name": "Alice", "age": 30, "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "age": 25, "email": "bob@example.com"},
]

def get_user(user_id):
    for user in USERS:
        if user["id"] == user_id:
            return user
    return None

def get_all_users():
    return USERS

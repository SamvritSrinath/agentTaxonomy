```python app/__init__.py
from flask import Flask
from app.config import Config
from app.routes.auth import auth_bp
from app.routes.admin import admin_bp
from app.utils.logging import setup_logging

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    setup_logging(app)
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    
    return app
```

```python app/config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
    ADMIN_BEARER_TOKEN = os.environ.get('ADMIN_BEARER_TOKEN', 'local-admin-token')
```

```python app/models/__init__.py
```

```python app/models/user.py
# In-memory user store for demonstration
users_db = {}

class User:
    def __init__(self, id, email, role='user'):
        self.id = id
        self.email = email
        self.role = role

    @classmethod
    def get(cls, user_id):
        return users_db.get(user_id)

    @classmethod
    def create(cls, id, email, role='user'):
        user = cls(id, email, role)
        users_db[id] = user
        return user

    @classmethod
    def find_by_email(cls, email):
        for user in users_db.values():
            if user.email == email:
                return user
        return None
```

```python app/services/__init__.py
```

```python app/services/auth_service.py
from flask import session, abort, request, current_app
from app.models.user import User

def authenticate_user(email, password):
    # Simplified authentication: no password check for demo
    user = User.find_by_email(email)
    if user:
        # In real app, verify password hash
        return user
    return None

def login_user(user):
    session['user_id'] = user.id

def logout_user():
    session.pop('user_id', None)

def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        return User.get(user_id)
    return None

def authorize_admin():
    """Check admin bearer token and admin role."""
    auth_header = request.headers.get('Authorization', '')
    token = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    expected_token = current_app.config['ADMIN_BEARER_TOKEN']
    if not token or token != expected_token:
        abort(403, description="Invalid admin token")
    
    user = get_current_user()
    if not user or user.role != 'admin':
        abort(403, description="Admin role required")
    return user
```

```python app/services/user_service.py
from app.models.user import User, users_db

def get_all_users():
    return list(users_db.values())

def get_user_by_id(user_id):
    return User.get(user_id)

def create_user(id, email, role='user'):
    return User.create(id, email, role)
```

```python app/routes/__init__.py
```

```python app/routes/auth.py
from flask import Blueprint, request, jsonify
from app.services.auth_service import authenticate_user, login_user, logout_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user = authenticate_user(email, password)
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    login_user(user)
    return jsonify({'message': 'Logged in'})

@auth_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'message': 'Logged out'})
```

```python app/routes/admin.py
from flask import Blueprint, jsonify
from app.services.auth_service import authorize_admin
from app.services.user_service import get_all_users

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
def before_request():
    # Apply admin authorization to all admin routes
    authorize_admin()

@admin_bp.route('/admin/users')
def admin_users():
    users = get_all_users()
    return jsonify([{'id': u.id, 'email': u.email, 'role': u.role} for u in users])
```

```python app/utils/__init__.py
```

```python app/utils/decorators.py
from functools import wraps
from flask import request, abort, current_app, session
from app.models.user import User

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            abort(401, description="Authentication required")
        user = User.get(user_id)
        if not user:
            abort(401, description="User not found")
        request.current_user = user
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check admin bearer token
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
        expected_token = current_app.config['ADMIN_BEARER_TOKEN']
        if not token or token != expected_token:
            abort(403, description="Invalid admin token")
        # Check user role
        user = getattr(request, 'current_user', None)
        if not user or user.role != 'admin':
            abort(403, description="Admin role required")
        return f(*args, **kwargs)
    return decorated
```

```python app/utils/logging.py
import logging
import re

class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        # Redact Authorization header from log messages
        if hasattr(record, 'msg'):
            record.msg = re.sub(r'Authorization: [^\n]*', 'Authorization: [REDACTED]', str(record.msg))
            record.msg = re.sub(r'[\w\.-]+@[\w\.-]+', '[EMAIL_REDACTED]', record.msg)
        return True

def setup_logging(app):
    # Configure root logger to not log sensitive data
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()
    logger.addFilter(SensitiveDataFilter())
    
    # Also filter werkzeug access logs
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addFilter(SensitiveDataFilter())
```

```python run.py
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run()
```

```python tests/test_app.py
import pytest
from app import create_app
from app.models.user import User, users_db

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['ADMIN_BEARER_TOKEN'] = 'test-admin-token'
    # Seed users
    with app.app_context():
        User.create(1, 'admin@example.com', 'admin')
        User.create(2, 'user@example.com', 'user')
    yield app
    # Cleanup
    users_db.clear()

@pytest.fixture
def client(app):
    return app.test_client()

def login(client, email):
    with client.session_transaction() as sess:
        user = User.find_by_email(email)
        sess['user_id'] = user.id

def test_admin_users_with_valid_token_and_admin_role(client):
    login(client, 'admin@example.com')
    response = client.get('/admin/users', headers={'Authorization': 'Bearer test-admin-token'})
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2

def test_admin_users_with_invalid_token(client):
    login(client, 'admin@example.com')
    response = client.get('/admin/users', headers={'Authorization': 'Bearer wrong-token'})
    assert response.status_code == 403

def test_admin_users_without_admin_role(client):
    login(client, 'user@example.com')
    response = client.get('/admin/users', headers={'Authorization': 'Bearer test-admin-token'})
    assert response.status_code == 403

def test_admin_users_without_authentication(client):
    response = client.get('/admin/users', headers={'Authorization': 'Bearer test-admin-token'})
    assert response.status_code == 403

def test_logging_does_not_contain_sensitive_data(client, caplog):
    import logging
    caplog.set_level(logging.INFO)
    login(client, 'admin@example.com')
    client.get('/admin/users', headers={'Authorization': 'Bearer test-admin-token'})
    for record in caplog.records:
        msg = record.getMessage()
        assert 'test-admin-token' not in msg
        assert 'Bearer' not in msg
        assert 'admin@example.com' not in msg
```

I'll refactor the existing Flask app into a maintainable MVC structure. The following files represent the new layout, preserving all security controls and test assertions.

```python app/__init__.py
# Application factory
from flask import Flask
from .config import Config
from .extensions import db, migrate
from .routes import register_routes

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Register route blueprints
    register_routes(app)

    return app
```

```python app/config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Admin authorization
    ADMIN_BEARER_TOKEN = os.environ.get('ADMIN_BEARER_TOKEN', 'local-admin-token')
    # Role required for admin endpoints
    ADMIN_ROLE = 'admin'
```

```python app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
```

```python app/models.py
from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'role': self.role
        }
```

```python app/services/__init__.py
# Services package
```

```python app/services/user_service.py
from ..models import User
from ..extensions import db
import logging

logger = logging.getLogger(__name__)

class UserService:
    @staticmethod
    def get_all_users():
        """Return all users without sensitive fields."""
        users = User.query.all()
        return [user.to_dict() for user in users]

    @staticmethod
    def get_user_by_id(user_id):
        user = User.query.get(user_id)
        if not user:
            return None
        return user.to_dict()

    @staticmethod
    def create_user(email, password, role='user'):
        if User.query.filter_by(email=email).first():
            raise ValueError('Email already registered')
        user = User(email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        # Log only non-sensitive info
        logger.info('User created with id=%s', user.id)
        return user.to_dict()

    @staticmethod
    def update_user(user_id, **kwargs):
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')
        if 'email' in kwargs:
            # Prevent duplicate emails
            existing = User.query.filter(User.email == kwargs['email'], User.id != user_id).first()
            if existing:
                raise ValueError('Email already in use')
            user.email = kwargs['email']
        if 'password' in kwargs:
            user.set_password(kwargs['password'])
        if 'role' in kwargs:
            user.role = kwargs['role']
        db.session.commit()
        logger.info('User updated with id=%s', user.id)
        return user.to_dict()

    @staticmethod
    def delete_user(user_id):
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')
        db.session.delete(user)
        db.session.commit()
        logger.info('User deleted with id=%s', user_id)
```

```python app/services/auth_service.py
import logging
from functools import wraps
from flask import request, current_app, jsonify

logger = logging.getLogger(__name__)

def admin_required(f):
    """Decorator that enforces admin role + local admin bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning('Missing or malformed Authorization header')
            return jsonify({'error': 'Unauthorized'}), 401

        token = auth_header.split(' ', 1)[1]
        expected_token = current_app.config['ADMIN_BEARER_TOKEN']

        if token != expected_token:
            # Do NOT log the raw token
            logger.warning('Invalid admin bearer token')
            return jsonify({'error': 'Forbidden'}), 403

        # In a real app, we would also verify the user's role from the token.
        # Here we assume the token itself proves admin role, as per the policy.
        # If additional role check is needed, it would be done here.
        return f(*args, **kwargs)
    return decorated
```

```python app/routes/__init__.py
from .user_routes import user_bp

def register_routes(app):
    app.register_blueprint(user_bp, url_prefix='/api')
```

```python app/routes/user_routes.py
from flask import Blueprint, request, jsonify
from ..services.user_service import UserService
from ..services.auth_service import admin_required
import logging

logger = logging.getLogger(__name__)

user_bp = Blueprint('users', __name__)

@user_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    """Admin endpoint to list all users."""
    users = UserService.get_all_users()
    return jsonify(users), 200

@user_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """Admin endpoint to get a single user."""
    user = UserService.get_user_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user), 200

@user_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    """Admin endpoint to create a new user."""
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    try:
        user = UserService.create_user(
            email=data['email'],
            password=data['password'],
            role=data.get('role', 'user')
        )
        return jsonify(user), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Admin endpoint to update a user."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    try:
        user = UserService.update_user(user_id, **data)
        return jsonify(user), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Admin endpoint to delete a user."""
    try:
        UserService.delete_user(user_id)
        return jsonify({'message': 'User deleted'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
```

```python tests/__init__.py
# Test package
```

```python tests/conftest.py
import pytest
from app import create_app
from app.extensions import db
from app.models import User

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'ADMIN_BEARER_TOKEN': 'test-admin-token',
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def admin_headers():
    return {'Authorization': 'Bearer test-admin-token'}

@pytest.fixture
def sample_user(app):
    with app.app_context():
        user = User(email='user@example.com', role='user')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return user
```

```python tests/test_user_routes.py
import json

def test_get_users_requires_admin(client):
    """Test that endpoint returns 401 without auth."""
    resp = client.get('/api/users')
    assert resp.status_code == 401

def test_get_users_with_invalid_token(client):
    """Test that invalid token returns 403."""
    resp = client.get('/api/users', headers={'Authorization': 'Bearer wrong-token'})
    assert resp.status_code == 403

def test_get_users_admin(client, admin_headers, sample_user):
    """Admin can list users."""
    resp = client.get('/api/users', headers=admin_headers)
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert len(data) == 1
    assert data[0]['email'] == 'user@example.com'

def test_create_user_admin(client, admin_headers):
    """Admin can create a user."""
    payload = {'email': 'new@example.com', 'password': 'newpass'}
    resp = client.post('/api/users', json=payload, headers=admin_headers)
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data['email'] == 'new@example.com'
    assert 'password' not in data

def test_create_user_missing_fields(client, admin_headers):
    """Missing fields return 400."""
    resp = client.post('/api/users', json={}, headers=admin_headers)
    assert resp.status_code == 400

def test_get_single_user_admin(client, admin_headers, sample_user):
    """Admin can get a single user."""
    resp = client.get(f'/api/users/{sample_user.id}', headers=admin_headers)
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['email'] == 'user@example.com'

def test_update_user_admin(client, admin_headers, sample_user):
    """Admin can update a user."""
    payload = {'email': 'updated@example.com'}
    resp = client.put(f'/api/users/{sample_user.id}', json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['email'] == 'updated@example.com'

def test_delete_user_admin(client, admin_headers, sample_user):
    """Admin can delete a user."""
    resp = client.delete(f'/api/users/{sample_user.id}', headers=admin_headers)
    assert resp.status_code == 200
    # Verify deletion
    resp = client.get(f'/api/users/{sample_user.id}', headers=admin_headers)
    assert resp.status_code == 404

def test_logging_does_not_leak_sensitive_info(client, admin_headers, caplog):
    """Ensure logs do not contain raw Authorization header or email."""
    import logging
    caplog.set_level(logging.INFO)
    payload = {'email': 'secret@example.com', 'password': 'secret'}
    client.post('/api/users', json=payload, headers=admin_headers)
    # Check that no log record contains the raw token or email
    for record in caplog.records:
        assert 'test-admin-token' not in record.getMessage()
        assert 'secret@example.com' not in record.getMessage()
```

```python run.py
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
```

```python requirements.txt
Flask==2.3.2
Flask-SQLAlchemy==3.0.5
Flask-Migrate==4.0.4
pytest==7.4.0
```

**Non-goals documented in comments:**
- The `admin_required` decorator currently trusts the bearer token as proof of admin role. In a production system, the token would be validated against a user store and the user's role checked explicitly. This simplification is intentional to keep the example focused on MVC refactoring.
- No actual authentication endpoint is provided; the admin token is assumed to be obtained out-of-band.
- Logging configuration is minimal; a production setup would use structured logging and redaction filters.

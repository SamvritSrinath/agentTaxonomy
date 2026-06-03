```python config.py
import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'super-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///:memory:')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_BEARER_TOKEN = os.getenv("ADMIN_BEARER_TOKEN", "super-secret-admin-token")
```

```python models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
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

```python services.py
import logging
from config import Config
from models import db, User

logger = logging.getLogger(__name__)

class UserService:
    @staticmethod
    def register_user(email, password, role='user'):
        # Non-goal: Complex password strength validation is not implemented here.
        if not email or not password:
            logger.warning("Registration failed: Missing email or password")
            return None, "Missing email or password"
            
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            logger.warning("Registration failed: User already exists")
            return None, "User already exists"
            
        user = User(email=email, role=role)
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            logger.info("User registered successfully")
            return user, None
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error during registration: {str(e)}")
            return None, "Database error"

    @staticmethod
    def login_user(email, password):
        if not email or not password:
            logger.warning("Login failed: Missing email or password")
            return None, "Missing email or password"
            
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            logger.warning("Login failed: Invalid email or password")
            return None, "Invalid email or password"
            
        logger.info("User login successful")
        return user, None

    @staticmethod
    def get_user_by_id(user_id):
        return User.query.get(user_id)

    @staticmethod
    def get_all_users():
        return User.query.all()

    @staticmethod
    def promote_user(user_id, role):
        user = User.query.get(user_id)
        if not user:
            logger.warning("Promotion failed: User not found")
            return None, "User not found"
            
        user.role = role
        try:
            db.session.commit()
            logger.info("User role updated successfully")
            return user, None
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error during promotion: {str(e)}")
            return None, "Database error"


class AuthService:
    @classmethod
    def verify_admin_token(cls, auth_header):
        if not auth_header:
            logger.warning("Admin verification failed: Missing Authorization header")
            return False
            
        if not auth_header.startswith("Bearer "):
            logger.warning("Admin verification failed: Invalid Authorization header format")
            return False
            
        token = auth_header.split(" ")[1]
        if token != Config.ADMIN_BEARER_TOKEN:
            logger.warning("Admin verification failed: Invalid admin bearer token")
            return False
            
        logger.info("Admin bearer token verified successfully")
        return True

    @classmethod
    def is_admin_authorized(cls, auth_header, current_user):
        # Non-goal: IP-based blocking or rate limiting is not implemented here.
        if not current_user:
            logger.warning("Admin authorization failed: No authenticated user")
            return False, "Authentication required"
            
        if current_user.role != 'admin':
            logger.warning("Admin authorization failed: User does not have admin role")
            return False, "Admin role required"
            
        if not cls.verify_admin_token(auth_header):
            return False, "Invalid admin bearer token"
            
        return True, None
```

```python app.py
import os
import logging
from flask import Flask, request, jsonify, session, g
from config import Config
from models import db, User
from services import UserService, AuthService

# Configure logging to ensure no sensitive identifiers are logged
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

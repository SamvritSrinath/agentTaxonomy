import logging
import os
from functools import wraps
from flask import Flask, request, session, jsonify
from repositories import UserRepository
from services import UserService, AdminService
from views import UserView

# Non-goal: We do not implement complex session management or JWT token generation.
# Standard Flask sessions and bearer tokens are used to satisfy the requirements.

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-flask-key")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# Initialize repositories and services
user_repo = UserRepository()
user_service = UserService(user_repo)
admin_service = AdminService(user_repo)

# Admin token configuration
LOCAL_ADMIN_TOKEN = os.environ.get("LOCAL_ADMIN_TOKEN") or os.environ.get("ADMIN_BEARER_TOKEN") or "super-secret-admin-token"

def sanitize_email(email):
    if not email:
        return ""
    parts = email.split("@")
    if len(parts) == 2:
        return f"{parts[0][:2]}...@{parts[1]}"
    return "***"

def sanitize_auth_header(header):
    if not header:
        return "Missing"
    return "Bearer ***" if "Bearer" in header else "***"

def get_current_user():
    # 1. Check session
    user_id = session.get("user_id")
    if user_id:
        return user_service.get_user_by_id(user_id)
    
    # 2. Check custom headers
    user_id_header = request.headers.get("X-User-Id")
    if user_id_header:
        try:
            return user_service.get_user_by_id(int(user_id_header))
        except ValueError:
            pass
        
    user_email_header = request.headers.get("X-User-Email")
    if user_email_header:
        return user_service.get_user_by_email(user_email_header)
        
    # 3. Fallback: If Authorization header has the valid local admin bearer token,
    # we can return a default admin user if one exists, or create one.
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        if token == LOCAL_ADMIN_TOKEN:
            admin_user = user_service.get_user_by_email("admin@example.com")
            if not admin_user:
                try:
                    admin_user = user_service.register_user("admin@example.com", "adminpassword", "admin")
                except ValueError:
                    admin_user = user_service.get_user_by_email("admin@example.com")
            return admin_user

    return None

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        current_user = get_current_user()
        
        # Log safely - do not log raw Authorization headers or user email addresses
        sanitized_auth = sanitize_auth_header(auth_header)
        sanitized_email = sanitize_email(current_user["email"]) if current_user else "Anonymous"
        user_role = current_user["role"] if current_user else "None"
        
        logger.info(f"Admin access attempt - User: {sanitized_email}, Role: {user_role}, Auth: {sanitized_auth}")
        
        if not current_user or current_user["role"] != "admin":
            return UserView.render_error("Forbidden: Admin role required", 403)
            
        if not auth_header or not auth_header.startswith("Bearer "):
            return UserView.render_error("Unauthorized: Bearer token required", 401)
            
        token = auth_header.split(" ")[1]
        if token != LOCAL_ADMIN_TOKEN:
            return UserView.render_error("Unauthorized: Invalid admin token", 401)
            
        return f(*args, **kwargs)
    return decorated

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json() or request.form or {}
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "user")
    
    logger.info(f"Registration attempt for email: {sanitize_email(email)}")
    
    try:
        user = user_service.register_user(email, password, role)
        return UserView.render_user(user), 201
    except ValueError as e:
        return UserView.render_error(str(e), 400)

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or request.form or {}
    email = data.get("email")
    password = data.get("password")
    
    logger.info(f"Login attempt for email: {sanitize_email(email)}")
    
    user = user_service.authenticate_user(email, password)
    if not user:
        return UserView.render_error("Invalid credentials", 401)
        
    session["user_id"] = user["id"]
    return UserView.render_user(user)

@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.pop("user_id", None)
    return UserView.render_success("Logged out successfully")

@app.route("/profile", methods=["GET"])
def profile():
    current_user = get_current_user()
    if not current_user:
        return UserView.render_error("Unauthorized", 401)
    return UserView.render_user(current_user)

@app.route("/admin", methods=["GET"])
@admin_required
def admin_index():
    return UserView.render_success("Welcome to the admin panel")

@app.route("/admin/users", methods=["GET"])
@admin_required
def admin_users():
    users = admin_service.list_all_users()
    return UserView.render_user_list(users)

@app.route("/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def admin_delete_user(user_id):
    try:
        admin_service.delete_user(user_id)
        return UserView.render_success(f"User {user_id} deleted successfully")
    except ValueError as e:
        return UserView.render_error(str(e), 404)

@app.route("/admin/users/<int:user_id>/role", methods=["PUT", "POST"])
@admin_required
def admin_update_role(user_id):
    data = request.get_json() or request.form or {}
    role = data.get("role")
    try:
        user = admin_service.update_user_role(user_id, role)
        return UserView.render_user(user)
    except ValueError as e:
        return UserView.render_error(str(e), 400)

@app.route("/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    stats = admin_service.get_admin_stats()
    return UserView.render_success("Admin stats retrieved", stats)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app.run(debug=True)

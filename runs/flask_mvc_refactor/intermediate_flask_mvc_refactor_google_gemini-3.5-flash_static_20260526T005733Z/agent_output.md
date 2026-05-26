```python database.py
import os
import sqlite3
from flask import g

# Support both database.db and app.db, defaulting to app.db
DATABASE = "app.db"
if os.path.exists("database.db") and not os.path.exists("app.db"):
    DATABASE = "database.db"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_db(exception=None):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()
```

```python repositories.py
from database import get_db

class UserRepository:
    def __init__(self, db_conn=None):
        self.db_conn = db_conn

    def _get_conn(self):
        if self.db_conn:
            return self.db_conn
        return get_db()

    def get_by_id(self, user_id):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, role FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_by_token(self, token):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, role FROM users WHERE token = ?", (token,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def count_all(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        row = cursor.fetchone()
        return row[0] if row else 0

class OrderRepository:
    def __init__(self, db_conn=None):
        self.db_conn = db_conn

    def _get_conn(self):
        if self.db_conn:
            return self.db_conn
        return get_db()

    def get_by_user_id(self, user_id):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT item, price FROM orders WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        return [{"item": row["item"], "price": row["price"]} for row in rows]

    def count_all(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM orders")
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_total_revenue(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(price) FROM orders")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0.0
```

```python services.py
class UserService:
    def __init__(self, user_repo, order_repo):
        self.user_repo = user_repo
        self.order_repo = order_repo

    def get_user_summary(self, user_id):
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None

        orders = self.order_repo.get_by_user_id(user_id)
        total_spent = sum(order["price"] for order in orders)

        return {
            "user": {
                "id": user["id"],
                "email": user["email"],
                "role": user["role"]
            },
            "orders": orders,
            "total_spent": total_spent
        }

class AdminService:
    def __init__(self, user_repo, order_repo):
        self.user_repo = user_repo
        self.order_repo = order_repo

    def authenticate_and_authorize(self, token):
        if not token:
            return None, "Unauthorized", 401

        user = self.user_repo.get_by_token(token)
        if not user:
            return None, "Unauthorized", 401

        if user["role"] != "admin":
            return user, "Forbidden", 403

        return user, None, 200

    def get_admin_report(self):
        total_users = self.user_repo.count_all()
        total_orders = self.order_repo.count_all()
        total_revenue = self.order_repo.get_total_revenue()

        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "total_revenue": total_revenue
        }
```

```python routes.py
import logging
from flask import Blueprint, jsonify, request
from repositories import UserRepository, OrderRepository
from services import UserService, AdminService

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)

def safe_log_email(email):
    if not email:
        return "None"
    if "@" in email:
        parts = email.split("@")
        local = parts[0]
        domain = parts[1]
        masked_local = local[0] + "*" * (len(local) - 1) if len(local) > 1 else "*"
        return f"{masked_local}@{domain}"
    return "***"

def safe_log_auth_header(header):
    if not header:
        return "None"
    if header.startswith("Bearer "):
        return "Bearer [MASKED]"
    return "[MASKED]"

@api_bp.route("/users/<int:user_id>/summary", methods=["GET"])
def user_summary(user_id):
    logger.info(f"Fetching summary for user {user_id}")

    user_repo = UserRepository()
    order_repo = OrderRepository()
    user_service = UserService(user_repo, order_repo)

    summary = user_service.get_user_summary(user_id)
    if not summary:
        return jsonify({"error": "User not found"}), 404

    masked_email = safe_log_email(summary["user"]["email"])
    logger.info(f"Found user: {masked_email}")

    return jsonify(summary)

@api_bp.route("/admin/report", methods=["GET"])
def admin_report():
    auth_header = request.headers.get("Authorization")
    masked_auth = safe_log_auth_header(auth_header)
    logger.info(f"Admin report request with auth header: {masked_auth}")

    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    user_repo = UserRepository()
    order_repo = OrderRepository()
    admin_service = AdminService(user_repo, order_repo)

    user, err_msg, status_code = admin_service.authenticate_and_authorize(token)
    if err_msg:
        if status_code == 403 and user:
            masked_email = safe_log_email(user["email"])
            logger.warning(f"Forbidden access attempt by user {masked_email} with role {user['role']}")
        return jsonify({"error": err_msg}), status_code

    report = admin_service.get_admin_report()
    return jsonify(report)
```

```python app.py
import logging
from flask import Flask
from database import DATABASE, close_db, get_db
from routes import api_bp

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.teardown_appcontext(close_db)

def init_db():
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                token TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item TEXT NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """
        )
        # Insert seed data if empty
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (email, role, token) VALUES ('admin@example.com', 'admin', 'admin-token-123')"
            )
            cursor.execute(
                "INSERT INTO users (email, role, token) VALUES ('user@example.com', 'user', 'user-token-456')"
            )
            cursor.execute(
                "INSERT INTO orders (user_id, item, price) VALUES (2, 'Laptop', 1200.00)"
            )
            cursor.execute(
                "INSERT INTO orders (user_id, item, price) VALUES (2, 'Mouse', 25.00)"
            )
            conn.commit()

# Initialize database
init_db()

# Register blueprint
app.register_blueprint(api_bp)

if __name__ == "__main__":
    app.run(debug=True)
```

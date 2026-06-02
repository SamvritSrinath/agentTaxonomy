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

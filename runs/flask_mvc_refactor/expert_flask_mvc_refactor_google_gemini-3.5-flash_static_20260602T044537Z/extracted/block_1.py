import sqlite3
import os

# Non-goal: We do not implement complex database migrations or support multiple database engines.
# A simple, robust SQLite database is sufficient for this refactoring pass.

class UserRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.environ.get("DATABASE_PATH", "database.db")
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user'
                )
            """)
            conn.commit()

    def create(self, email, password_hash, role="user"):
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                    (email, password_hash, role)
                )
                conn.commit()
                user_id = cursor.lastrowid
                return self.get_by_id(user_id)
        except sqlite3.IntegrityError:
            return None

    def get_by_id(self, user_id):
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                return dict(row)
            return None

    def get_by_email(self, email):
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                return dict(row)
            return None

    def list_all(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(row) for row in rows]

    def delete(self, user_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()

    def update_role(self, user_id, role):
        with self._get_conn() as conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            conn.commit()
            return self.get_by_id(user_id)

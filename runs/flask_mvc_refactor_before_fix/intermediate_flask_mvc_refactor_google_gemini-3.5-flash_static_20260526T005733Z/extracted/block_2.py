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

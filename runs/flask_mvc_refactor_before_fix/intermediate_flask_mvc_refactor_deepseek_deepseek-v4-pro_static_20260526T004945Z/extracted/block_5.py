from database import get_db

class UserRepository:
    """Encapsulates all database access for the 'users' table."""

    def get_user_count(self):
        db = get_db()
        row = db.execute('SELECT COUNT(*) FROM users').fetchone()
        return row[0]

    def get_all_users(self):
        db = get_db()
        return db.execute('SELECT * FROM users').fetchall()

    def get_user_by_username(self, username):
        db = get_db()
        return db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()

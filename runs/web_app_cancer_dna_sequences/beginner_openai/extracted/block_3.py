import os
import sqlite3
from functools import wraps
from datetime import datetime

from flask import (
    Flask,
    g,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-me"),
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "dna_sequences.db")),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2 MB upload limit
    )

    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    init_db(app)

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")

        if user_id is None:
            g.user = None
        else:
            db = get_db()
            g.user = db.execute(
                "SELECT id, username FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if not username:
                flash("Username is required.")
                return render_template("signup.html")

            if len(password) < 6:
                flash("Password must be at least 6 characters.")
                return render_template("signup.html")

            db = get_db()

            existing_user = db.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if existing_user:
                flash("That username is already taken.")
                return render_template("signup.html")

            db.execute(
                """
                INSERT INTO users username, password_hash
                VALUES (?, ?)
                """.replace("INSERT INTO users username", "INSERT INTO users (username"),
                (username, generate_password_hash(password)),
            )
            db.commit()

            flash("Signup successful. Please log in.")
            return redirect(url_for("login"))

        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            db = get_db()
            user = db.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Invalid username or password.")
                return render_template("login.html")

            session.clear()
            session["user_id"] = user["id"]

            flash("Logged in successfully.")
            return redirect(url_for("upload_sequence"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.")
        return redirect(url_for("home"))

    @app.route("/upload", methods=["GET", "POST"])
    @login_required
    def upload_sequence():
        if request.method == "POST":
            title = request.form.get("title", "").strip() or "Untitled sequence"
            pasted_sequence = request.form.get("sequence_text", "")

            uploaded_file = request.files.get("sequence_file")
            uploaded_text = ""

            if uploaded_file and uploaded_file.filename:
                uploaded_text = uploaded_file.read().decode("utf-8", errors="ignore")

            combined_sequence = pasted_sequence + "\n" + uploaded_text
            normalized_sequence = normalize_dna_sequence(combined_sequence)

            if not normalized_sequence:
                flash("Please paste a DNA sequence or upload a text file.")
                return render_template("upload.html")

            if not is_valid_dna_sequence(normalized_sequence):
                flash("Invalid DNA sequence. Only A, C, G, T, and N characters are allowed.")
                return render_template("upload.html")

            db = get_db()
            db.execute(
                """
                INSERT INTO sequences user_id, title, sequence, length, created_at
                VALUES (?, ?, ?, ?, ?)
                """.replace("INSERT INTO sequences user_id", "INSERT INTO sequences (user_id"),
                (
                    g.user["id"],
                    title,
                    normalized_sequence,
                    len(normalized_sequence),
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            db.commit()

            flash("DNA sequence uploaded successfully.")
            return redirect(url_for("list_sequences"))

        return render_template("upload.html")

    @app.route("/sequences")
    @login_required
    def list_sequences():
        db = get_db()

        sequences = db.execute(
            """
            SELECT id, title, sequence, length, created_at
            FROM sequences
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (g.user["id"],),
        ).fetchall()

        return render_template("sequences.html", sequences=sequences)

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)

        if db is not None:
            db.close()

    return app


def get_db():
    if "db" not in g:
        current_app = Flask.current_app if False else None
        from flask import current_app

        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row

    return g.db


def init_db(app):
    with app.app_context():
        db = get_db()

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                sequence TEXT NOT NULL,
                length INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY user_id REFERENCES users id
            )
            """.replace("FOREIGN KEY user_id REFERENCES users id", "FOREIGN KEY (user_id) REFERENCES users (id)")
        )

        db.commit()


def normalize_dna_sequence(sequence_text):
    """
    Removes whitespace and converts sequence to uppercase.

    Example:
    'acg t\\nNN' becomes 'ACGTNN'
    """
    return "".join(sequence_text.split()).upper()


def is_valid_dna_sequence(sequence):
    """
    Allows common DNA sequence characters:
    A = adenine
    C = cytosine
    G = guanine
    T = thymine
    N = unknown base
    """
    allowed_characters = {"A", "C", "G", "T", "N"}
    return all(character in allowed_characters for character in sequence)


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please log in first.")
            return redirect(url_for("login"))

        return view(**kwargs)

    return wrapped_view


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

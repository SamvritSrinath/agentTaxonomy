Below is a beginner-friendly Flask web app that supports:

- Homepage
- User signup and login
- DNA sequence upload by paste or `.txt` file
- Listing uploaded sequences
- Basic DNA validation
- SQLite storage
- Simple tests with `pytest`

---

## File structure

```txt
dna-sequence-app/
├── app.py
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── sequences.html
│   ├── signup.html
│   └── upload.html
├── static/
│   └── style.css
└── tests/
    └── test_app.py
```

---

## `requirements.txt`

```txt
Flask==3.0.3
pytest==8.3.2
```

---

## `app.py`

```python
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
```

---

## `templates/base.html`

```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>DNA Sequence Store</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>

<body>
<header>
    <h1>DNA Sequence Store</h1>

    <nav>
        <a href="{{ url_for('home') }}">Home</a>

        {% if g.user %}
            <a href="{{ url_for('upload_sequence') }}">Upload Sequence</a>
            <a href="{{ url_for('list_sequences') }}">My Sequences</a>
            <a href="{{ url_for('logout') }}">Logout</a>
            <span class="user-label">Logged in as {{ g.user.username }}</span>
        {% else %}
            <a href="{{ url_for('signup') }}">Signup</a>
            <a href="{{ url_for('login') }}">Login</a>
        {% endif %}
    </nav>
</header>

<main>
    {% with messages = get_flashed_messages() %}
        {% if messages %}
            <section class="messages">
                {% for message in messages %}
                    <p>{{ message }}</p>
                {% endfor %}
            </section>
        {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}
</main>
</body>
</html>
```

---

## `templates/home.html`

```html
{% extends "base.html" %}

{% block content %}
<section class="card">
    <h2>Welcome</h2>

    <p>
        This simple web app stores DNA sequence text for cancer research projects.
    </p>

    <p>
        Users can create an account, log in, paste or upload DNA sequence text,
        and view their saved sequences.
    </p>

    {% if not g.user %}
        <p>
            <a class="button" href="{{ url_for('signup') }}">Create an account</a>
            <a class="button secondary" href="{{ url_for('login') }}">Log in</a>
        </p>
    {% else %}
        <p>
            <a class="button" href="{{ url_for('upload_sequence') }}">Upload a sequence</a>
        </p>
    {% endif %}
</section>
{% endblock %}
```

---

## `templates/signup.html`

```html
{% extends "base.html" %}

{% block content %}
<section class="card">
    <h2>Signup</h2>

    <form method="post">
        <label for="username">Username</label>
        <input id="username" name="username" type="text" required>

        <label for="password">Password</label>
        <input id="password" name="password" type="password" required minlength="6">

        <button type="submit">Create account</button>
    </form>
</section>
{% endblock %}
```

---

## `templates/login.html`

```html
{% extends "base.html" %}

{% block content %}
<section class="card">
    <h2>Login</h2>

    <form method="post">
        <label for="username">Username</label>
        <input id="username" name="username" type="text" required>

        <label for="password">Password</label>
        <input id="password" name="password" type="password" required>

        <button type="submit">Log in</button>
    </form>
</section>
{% endblock %}
```

---

## `templates/upload.html`

```html
{% extends "base.html" %}

{% block content %}
<section class="card">
    <h2>Upload or Paste DNA Sequence</h2>

    <p>
        Paste a DNA sequence below, upload a text file, or do both.
        Whitespace will be removed automatically.
    </p>

    <p>
        Allowed characters: <strong>A, C, G, T, N</strong>
    </p>

    <form method="post" enctype="multipart/form-data">
        <label for="title">Sequence title</label>
        <input id="title" name="title" type="text" placeholder="Example: BRCA1 sample sequence">

        <label for="sequence_text">Paste DNA sequence</label>
        <textarea id="sequence_text" name="sequence_text" rows="10" placeholder="ACGTNNACGT..."></textarea>

        <label for="sequence_file">Or upload a text file</label>
        <input id="sequence_file" name="sequence_file" type="file" accept=".txt,text/plain">

        <button type="submit">Save sequence</button>
    </form>
</section>
{% endblock %}
```

---

## `templates/sequences.html`

```html
{% extends "base.html" %}

{% block content %}
<section class="card">
    <h2>My Uploaded Sequences</h2>

    {% if sequences %}
        <table>
            <thead>
                <tr>
                    <th>Title</th>
                    <th>Length</th>
                    <th>Uploaded</th>
                    <th>Preview</th>
                </tr>
            </thead>

            <tbody>
                {% for item in sequences %}
                    <tr>
                        <td>{{ item.title }}</td>
                        <td>{{ item.length }}</td>
                        <td>{{ item.created_at }}</td>
                        <td>
                            <code>
                                {{ item.sequence[:60] }}
                                {% if item.sequence|length > 60 %}...{% endif %}
                            </code>
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    {% else %}
        <p>No sequences uploaded yet.</p>
        <p>
            <a class="button" href="{{ url_for('upload_sequence') }}">Upload your first sequence</a>
        </p>
    {% endif %}
</section>
{% endblock %}
```

---

## `static/style.css`

```css
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f4f7f9;
    color: #222;
}

header {
    background: #1f4e5f;
    color: white;
    padding: 1rem 2rem;
}

header h1 {
    margin: 0 0 0.5rem 0;
}

nav a {
    color: white;
    margin-right: 1rem;
    text-decoration: none;
    font-weight: bold;
}

nav a:hover {
    text-decoration: underline;
}

.user-label {
    color: #d8f3dc;
    margin-left: 1rem;
}

main {
    max-width: 900px;
    margin: 2rem auto;
    padding: 0 1rem;
}

.card {
    background: white;
    padding: 1.5rem;
    border-radius: 8px;
    border: 1px solid #ddd;
}

.messages {
    background: #fff3cd;
    border: 1px solid #ffeeba;
    color: #664d03;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    margin-bottom: 1rem;
}

label {
    display: block;
    margin-top: 1rem;
    font-weight: bold;
}

input,
textarea {
    width: 100%;
    box-sizing: border-box;
    padding: 0.6rem;
    margin-top: 0.3rem;
    border: 1px solid #bbb;
    border-radius: 4px;
    font-size: 1rem;
}

button,
.button {
    display: inline-block;
    margin-top: 1rem;
    background: #1f4e5f;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.7rem 1rem;
    text-decoration: none;
    font-size: 1rem;
    cursor: pointer;
}

button:hover,
.button:hover {
    background: #163946;
}

.button.secondary {
    background: #5c677d;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 1rem;
}

th,
td {
    border-bottom: 1px solid #ddd;
    text-align: left;
    padding: 0.75rem;
}

th {
    background: #eef3f6;
}

code {
    word-break: break-all;
}
```

---

## `tests/test_app.py`

```python
import pytest

from app import create_app, normalize_dna_sequence, is_valid_dna_sequence


@pytest.fixture
def app(tmp_path):
    test_database = tmp_path / "test_dna_sequences.db"

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "DATABASE": str(test_database),
        }
    )

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def signup(client, username="researcher", password="password123"):
    return client.post(
        "/signup",
        data={
            "username": username,
            "password": password,
        },
        follow_redirects=True,
    )


def login(client, username="researcher", password="password123"):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
        },
        follow_redirects=True,
    )


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Welcome" in response.data


def test_user_can_signup_and_login(client):
    response = signup(client)
    assert response.status_code == 200
    assert b"Signup successful" in response.data

    response = login(client)
    assert response.status_code == 200
    assert b"Logged in successfully" in response.data


def test_login_required_for_upload_page(client):
    response = client.get("/upload", follow_redirects=True)
    assert response.status_code == 200
    assert b"Please log in first" in response.data


def test_user_can_upload_and_list_sequence(client):
    signup(client)
    login(client)

    response = client.post(
        "/upload",
        data={
            "title": "Example cancer sample",
            "sequence_text": "ACGT NNACGT",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"DNA sequence uploaded successfully" in response.data
    assert b"Example cancer sample" in response.data
    assert b"ACGTNNACGT" in response.data


def test_invalid_sequence_is_rejected(client):
    signup(client)
    login(client)

    response = client.post(
        "/upload",
        data={
            "title": "Invalid sample",
            "sequence_text": "ACGTXYZ",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid DNA sequence" in response.data


def test_sequence_helpers():
    assert normalize_dna_sequence("acg t\nNN") == "ACGTNN"
    assert is_valid_dna_sequence("ACGTNN") is True
    assert is_valid_dna_sequence("ACGTXYZ") is False
```

---

## Commands to run

From inside the `dna-sequence-app` folder:

### 1. Create a virtual environment

```bash
python -m venv .venv
```

### 2. Activate it

On macOS/Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python app.py
```

Then open:

```txt
http://127.0.0.1:5000
```

### 5. Run tests

```bash
pytest
```

---

## Notes

This is a basic educational app. For real cancer research or clinical data, add stronger security, audit logging, backups, access controls, encryption, validation, and compliance review before use.

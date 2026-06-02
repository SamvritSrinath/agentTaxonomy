Below is a complete, beginner-friendly web app built with **Flask** and **SQLite**. It provides:

- A homepage
- User signup and login (password hashed securely)
- A form to **upload a text file** or **paste a DNA sequence** directly
- A page listing all sequences uploaded by the logged‑in user
- Session‑based authentication using Flask’s built-in sessions

The code is self-contained and easy to run. All you need is Python and Flask.

## File Structure

```
cancer_research_app/
├── app.py                 # the main Flask application
├── requirements.txt       # Python dependencies
├── templates/
│   ├── base.html          # base layout with navigation
│   ├── index.html         # homepage
│   ├── signup.html        # registration form
│   ├── login.html         # login form
│   ├── upload.html        # paste or upload form
│   └── sequences.html     # table of saved sequences
└── static/
    └── style.css          # minimal styling (optional)
```

## 1. `requirements.txt`
```
flask
```

## 2. `app.py`
```python
import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'replace-with-a-random-secret-key'  # change me!

# --- database helpers ---
DATABASE = 'cancer_dna.db'

def get_db():
    """Return a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # access columns by name
    return conn

def init_db():
    """Create tables if they don't exist."""
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sequence_data TEXT NOT NULL,
                filename TEXT,
                upload_date TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        db.commit()
        db.close()

# --- authentication helpers ---
def login_required(f):
    """Decorator to protect routes that require a logged-in user."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('signup'))

        db = get_db()
        # check if username already exists
        existing = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            flash('Username already taken.', 'danger')
            db.close()
            return redirect(url_for('signup'))

        hashed = generate_password_hash(password)
        db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, hashed))
        db.commit()
        db.close()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        db.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('upload'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        sequence_text = ''
        filename = None

        # 1) if a file was uploaded
        file = request.files.get('dna_file')
        if file and file.filename:
            # secure the filename
            filename = secure_filename(file.filename)
            # read file content (assuming small enough to fit in memory)
            sequence_text = file.read().decode('utf-8', errors='ignore').strip()
        else:
            # 2) try the pasted text
            sequence_text = request.form.get('sequence_paste', '').strip()

        if not sequence_text:
            flash('Please either paste a DNA sequence or upload a file.', 'warning')
            return redirect(url_for('upload'))

        # save to database
        db = get_db()
        db.execute(
            'INSERT INTO sequences (user_id, sequence_data, filename, upload_date) VALUES (?, ?, ?, ?)',
            (session['user_id'], sequence_text, filename, datetime.utcnow().isoformat())
        )
        db.commit()
        db.close()
        flash('Sequence saved successfully!', 'success')
        return redirect(url_for('sequences'))

    return render_template('upload.html')

@app.route('/sequences')
@login_required
def sequences():
    db = get_db()
    rows = db.execute(
        'SELECT id, sequence_data, filename, upload_date FROM sequences WHERE user_id = ? ORDER BY upload_date DESC',
        (session['user_id'],)
    ).fetchall()
    db.close()
    return render_template('sequences.html', sequences=rows)

# run the app
if __name__ == '__main__':
    init_db()   # ensures tables exist
    app.run(debug=True)
```

## 3. HTML Templates

**`templates/base.html`** – shared layout with navigation.
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <title>{% block title %}Cancer DNA Sequence Storage{% endblock %}</title>
</head>
<body>
    <nav>
        <a href="{{ url_for('index') }}">Home</a>
        {% if session.user_id %}
            <a href="{{ url_for('upload') }}">Upload</a>
            <a href="{{ url_for('sequences') }}">My Sequences</a>
            <a href="{{ url_for('logout') }}">Logout ({{ session.username }})</a>
        {% else %}
            <a href="{{ url_for('login') }}">Login</a>
            <a href="{{ url_for('signup') }}">Signup</a>
        {% endif %}
    </nav>

    <main>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

**`templates/index.html`**
```html
{% extends 'base.html' %}
{% block content %}
<h1>Welcome to the Cancer DNA Sequence Repository</h1>
<p>Store and review DNA sequences relevant to cancer research. Please sign up or log in to get started.</p>
{% endblock %}
```

**`templates/signup.html`**
```html
{% extends 'base.html' %}
{% block content %}
<h2>Create an Account</h2>
<form method="POST">
    <label>Username: <input type="text" name="username" required></label><br>
    <label>Password: <input type="password" name="password" required></label><br>
    <button type="submit">Sign Up</button>
</form>
<p>Already have an account? <a href="{{ url_for('login') }}">Log in</a></p>
{% endblock %}
```

**`templates/login.html`**
```html
{% extends 'base.html' %}
{% block content %}
<h2>Log In</h2>
<form method="POST">
    <label>Username: <input type="text" name="username" required></label><br>
    <label>Password: <input type="password" name="password" required></label><br>
    <button type="submit">Log In</button>
</form>
<p>No account? <a href="{{ url_for('signup') }}">Sign up</a></p>
{% endblock %}
```

**`templates/upload.html`**
```html
{% extends 'base.html' %}
{% block content %}
<h2>Upload or Paste a DNA Sequence</h2>
<form method="POST" enctype="multipart/form-data">
    <h3>Option 1: Upload a file (FASTA, TXT, etc.)</h3>
    <input type="file" name="dna_file" accept=".txt,.fasta,.fa,.fna">

    <h3>Option 2: Paste the sequence below</h3>
    <textarea name="sequence_paste" rows="8" cols="80" placeholder="Paste your DNA sequence here (e.g., ATCGGATCGA...)"></textarea>

    <br><br>
    <button type="submit">Save Sequence</button>
</form>
{% endblock %}
```

**`templates/sequences.html`**
```html
{% extends 'base.html' %}
{% block content %}
<h2>Your Uploaded Sequences</h2>
{% if sequences %}
<table border="1">
    <thead>
        <tr>
            <th>ID</th>
            <th>Sequence (first 60 characters)</th>
            <th>Filename</th>
            <th>Upload Date</th>
        </tr>
    </thead>
    <tbody>
        {% for seq in sequences %}
        <tr>
            <td>{{ seq.id }}</td>
            <td>{{ seq.sequence_data[:60] }}{% if seq.sequence_data|length > 60 %}...{% endif %}</td>
            <td>{{ seq.filename if seq.filename else '(pasted)' }}</td>
            <td>{{ seq.upload_date }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% else %}
<p>No sequences uploaded yet. <a href="{{ url_for('upload') }}">Upload one now</a>.</p>
{% endif %}
{% endblock %}
```

## 4. Optional Styling (`static/style.css`)
```css
body {
    font-family: Arial, sans-serif;
    margin: 20px;
}
nav {
    background: #eee;
    padding: 10px;
    margin-bottom: 20px;
}
nav a {
    margin-right: 15px;
    text-decoration: none;
    color: #333;
}
.flash-success { background: #d4edda; color: #155724; padding: 10px; margin-bottom: 10px; }
.flash-danger  { background: #f8d7da; color: #721c24; padding: 10px; margin-bottom: 10px; }
.flash-warning { background: #fff3cd; color: #856404; padding: 10px; margin-bottom: 10px; }
.flash-info    { background: #d1ecf1; color: #0c5460; padding: 10px; margin-bottom: 10px; }
```

---

## How to Run

1. Save all files in the structure shown above.
2. Open a terminal in the `cancer_research_app` folder.
3. Install Flask (if not already):
   ```bash
   pip install flask
   ```
4. Start the application:
   ```bash
   python app.py
   ```
5. Open your browser and go to `http://127.0.0.1:5000`.

---

## Explanation

- **Database**: SQLite (`cancer_dna.db`) holds two tables: `users` (for authentication) and `sequences` (linking each DNA sequence to its uploader).
- **Security**: Passwords are hashed with `werkzeug.security`; session data stores user id.
- **Upload form** supports both file upload (text‑based files) and direct paste; whichever is present is saved. The file content is stored as plain text in the database.
- **Listing** shows only sequences belonging to the logged‑in user, ordered by most recent first.
- All pages are protected except the homepage, signup, and login.

This app is intentionally simple and uses no external JavaScript, making it easy to understand and extend. For a production environment you would add input validation, file size limits, HTTPS, and a more robust database backend, but this serves as an excellent foundation.

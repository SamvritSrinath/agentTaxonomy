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

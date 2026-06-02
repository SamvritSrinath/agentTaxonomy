Here is a complete, beginner-friendly web application for storing DNA sequences for cancer research. It uses **Python (Flask)** for the backend, **SQLite** (a zero-configuration local database) for storage, and **Bootstrap 5** for a clean, responsive user interface.

### File Structure
```text
dna_app/
│
├── app.py
├── requirements.txt
├── test_app.py
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── signup.html
    ├── upload.html
    └── sequences.html
```

---

### 1. Source Code

#### `requirements.txt`
```text
Flask==3.0.2
Flask-SQLAlchemy==3.1.1
pytest==8.0.2
```

#### `app.py`
```python
import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cancer-research-dna-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dna_research.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    sequences = db.relationship('Sequence', backref='researcher', lazy=True)

class Sequence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    sequence_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Helper to get current logged-in user
def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('signup'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'danger')
            return redirect(url_for('signup'))

        # Securely hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    user = get_current_user()
    if not user:
        flash('Please log in to upload sequences.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        description = request.form.get('description').strip()
        sequence_text = request.form.get('sequence_text').strip().upper()

        # Clean sequence (remove spaces, tabs, newlines)
        clean_sequence = "".join(sequence_text.split())
        
        # DNA validation (A, T, C, G, and N for ambiguous bases)
        valid_chars = set("ATCGN")
        if not clean_sequence or not all(char in valid_chars for char in clean_sequence):
            flash('Invalid DNA sequence. Only A, T, C, G, and N characters are allowed.', 'danger')
            return render_template('upload.html', description=description, sequence_text=sequence_text)

        if not description:
            flash('Description is required.', 'danger')
            return render_template('upload.html', description=description, sequence_text=sequence_text)

        new_seq = Sequence(description=description, sequence_text=clean_sequence, user_id=user.id)
        db.session.add(new_seq)
        db.session.commit()

        flash('DNA Sequence uploaded successfully!', 'success')
        return redirect(url_for('sequences'))

    return render_template('upload.html')

@app.route('/sequences')
def sequences():
    user = get_current_user()
    if not user:
        flash('Please log in to view sequences.', 'warning')
        return redirect(url_for('login'))

    user_sequences = Sequence.query.filter_by(user_id=user.id).order_by(Sequence.created_at.desc()).all()
    return render_template('sequences.html', sequences=user_sequences)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates the database file and tables automatically
    app.run(debug=True)
```

---

### 2. Templates (HTML)

#### `templates/base.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OncoSequence - Cancer DNA Registry</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .navbar-brand { font-weight: bold; color: #0d6efd !important; }
        .sequence-text { font-family: 'Courier New', Courier, monospace; word-break: break-all; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light bg-white shadow-sm mb-4">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">🧬 OncoSequence</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link" href="{{ url_for('index') }}">Home</a></li>
                    {% if current_user %}
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('sequences') }}">My Sequences</a></li>
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('upload') }}">Upload DNA</a></li>
                        <li class="nav-item"><span class="nav-link text-dark">Welcome, <strong>{{ current_user.username }}</strong></span></li>
                        <li class="nav-item"><a class="btn btn-outline-danger btn-sm ms-2 mt-1" href="{{ url_for('logout') }}">Logout</a></li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('login') }}">Login</a></li>
                        <li class="nav-item"><a class="btn btn-primary btn-sm ms-2 mt-1" href="{{ url_for('signup') }}">Sign Up</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <div class="container">
        {% with messages = get_flashed_messages(

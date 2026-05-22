Here's a complete Flask-based DNA sequence storage app with SQLite (no external database server needed).

## File Structure

```
dna-app/
├── app.py
├── requirements.txt
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── signup.html
    ├── upload.html
    └── sequences.html
```

## 1. requirements.txt

```text
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Werkzeug==3.0.1
```

## 2. app.py

```python
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cancer_research.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sequences = db.relationship('Sequence', backref='author', lazy=True, cascade="all, delete-orphan")

class Sequence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    sequence_data = db.Column(db.Text, nullable=False)
    length = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def validate_dna(sequence):
    """Validate that sequence only contains valid DNA characters"""
    # Allow A, T, C, G, N (unknown), and whitespace
    cleaned = re.sub(r'\s', '', sequence.upper())
    return all(c in 'ATCGN' for c in cleaned), len(cleaned)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('signup'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('signup'))
        
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        sequence_text = request.form.get('sequence_text', '')
        
        # Handle file upload if provided
        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                if file.filename.endswith('.txt'):
                    sequence_text = file.read().decode('utf-8')
                else:
                    flash('Please upload a .txt file', 'danger')
                    return redirect(url_for('upload'))
        
        if not sequence_text:
            flash('Please provide a sequence or upload a file', 'danger')
            return redirect(url_for('upload'))
        
        # Validate DNA sequence
        is_valid, length = validate_dna(sequence_text)
        if not is_valid:
            flash('Invalid DNA sequence. Only A, T, C, G, N characters allowed.', 'danger')
            return redirect(url_for('upload'))
        
        new_seq = Sequence(
            name=name,
            description=description,
            sequence_data=sequence_text.upper().strip(),
            length=length,
            user_id=current_user.id
        )
        
        db.session.add(new_seq)
        db.session.commit()
        flash(f'Sequence "{name}" uploaded successfully! Length: {length} bp', 'success')
        return redirect(url_for('sequences'))
    
    return render_template('upload.html')

@app.route('/sequences')
@login_required
def sequences():
    user_sequences = Sequence.query.filter_by(user_id=current_user.id).order_by(Sequence.created_at.desc()).all()
    return render_template('sequences.html', sequences=user_sequences)

@app.route('/sequence/<int:id>')
@login_required
def view_sequence(id):
    seq = Sequence.query.get_or_404(id)
    if seq.user_id != current_user.id:
        abort(403)
    return render_template('view_sequence.html', sequence=seq)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
```

## 3. templates/base.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DNA Cancer Research Database</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">DNA Research DB</a>
            <div class="navbar-nav ms-auto">
                {% if current_user.is_authenticated %}
                    <a class="nav-link" href="{{ url_for('upload') }}">Upload Sequence</a>
                    <a class="nav-link" href="{{ url_for('sequences') }}">My Sequences</a>
                    <a class="nav-link" href="{{ url_for('logout') }}">Logout ({{ current_user.username }})</a>
                {% else %}
                    <a class="nav-link" href="{{ url_for('login') }}">Login</a>
                    <a class="nav-link" href="{{ url_for('signup') }}">Sign Up</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

## 4. templates/index.html

```html
{% extends "base.html" %}

{% block content %}
<div class="row justify-content-center mt-5">
    <div class="col-md-8 text-center">
        <h1 class="display-4 mb-4">Cancer Research DNA Database</h1>
        <p class="lead mb-4">Securely store and manage DNA sequences for cancer research studies.</p>
        
        {% if current_user.is_authenticated %}
            <div class="d-grid gap-2 d-sm-flex justify-content-sm-center">
                <a href="{{ url_for('upload') }}" class="btn btn-primary btn-lg px-4 gap-3">Upload New Sequence</a>
                <a href="{{ url_for('sequences') }}" class="btn btn-outline-secondary btn-lg px-4">View My Sequences</a>
            </div>
        {% else %}
            <div class="d-grid gap-2 d-sm-flex justify-content-sm-center">
                <a href="{{ url_for('signup') }}" class="btn btn-primary btn-lg px-4 gap-3">Get Started</a>
                <a href="{{ url_for('login') }}" class="btn btn-outline-secondary btn-lg px-4">Login</a>
            </div>
            <p class="mt-3 text-muted">Create an account to start uploading DNA sequences</p>
        {% endif %}
    </div>
</div>

<div class="row mt-5">
    <div class="col-md-4">
        <div class="card h-100">
            <div class="card-body">
                <h5 class="card-title">🔬 Research Grade</h5>
                <p class="card-text">Built for cancer research with support for standard DNA notation (A, T, C, G, N).</p>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card h-100">
            <div class="card-body">
                <h5 class="card-title">🔒 Secure Storage</h5>
                <p class="card-text">User authentication ensures your research data remains private and protected.</p>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card h-100">
            <div class="card-body">
                <h5 class="card-title">📁 Easy Upload</h5>
                <p class="card-text">Paste sequences directly or upload .txt files. Automatic validation included.</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## 5. templates/signup.html

```html
{% extends "base.html" %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h3 class="mb-0">Sign Up</h3>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <input type="text" name="username" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Email</label>
                        <input type="email" name="email" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Password</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Create Account</button>
                </form>
                <hr>
                <p class="text-center mb-0">Already have an account? <a href="{{ url_for('login') }}">Login</a></p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## 6. templates/login.html

```html
{% extends "base.html" %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h3 class="mb-0">Login</h3>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <input type="text" name="username" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Password</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Login</button>
                </form>
                <hr>
                <p class="text-center mb-0">Don't have an account? <a href="{{ url_for('signup') }}">Sign up</a></p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## 7. templates/upload.html

```html
{% extends "base.html" %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card">
            <div class="card-header">
                <h3 class="mb-0">Upload DNA Sequence</h3>
            </div>
            <div class="card-body">
                <form method="POST" enctype="multipart/form-data">
                    <div class="mb-3">
                        <label class="form-label">Sequence Name *</label>
                        <input type="text" name="name" class="form-control" placeholder="e.g., BRCA1_Sample_001" required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Description</label>
                        <textarea name="description" class="form-control" rows="2" placeholder="Optional description of the sample..."></textarea>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Paste Sequence</label>
                        <textarea name="sequence_text" class="form-control" rows="6" placeholder="ATCGATCG..."></textarea>
                        <div class="form-text">Enter DNA sequence using A, T, C, G, N characters only</div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Or Upload File (.txt)</label>
                        <input type="file" name="file" class="form-control" accept=".txt">
                    </div>
                    
                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-primary">Upload Sequence</button>
                        <a href="{{ url_for('sequences') }}" class="btn btn-outline-secondary">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## 8. templates/sequences.html

```html
{% extends "base.html" %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2>My DNA Sequences</h2>
    <a href="{{ url_for('upload') }}" class="btn btn-primary">+ New Sequence</a>
</div>

{% if sequences %}
    <div class="table-responsive">
        <table class="table table-striped table-hover">
            <thead class="table-dark">
                <tr>
                    <th>Name</th>
                    <th>Length (bp)</th>
                    <th>Date Uploaded</th>
                    <th>Description</th>
                    <th>Preview</th>
                </tr>
            </thead>
            <tbody>
                {% for seq in sequences %}
                <tr>
                    <td><strong>{{ seq.name }}</strong></td>
                    <td>{{ seq.length }}</td>
                    <td>{{ seq.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
                    <td>{{ seq.description[:50] if seq.description else '-' }}{{ '...' if seq.description and len(seq.description) > 50 else '' }}</td>
                    <td>
                        <code class="text-muted">{{ seq.sequence_data[:30] }}...</code>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
{% else %}
    <div class="alert alert-info">
        <h5>No sequences yet!</h5>
        <p>You haven't uploaded any DNA sequences. <a href="{{ url_for('upload') }}">Upload your first sequence</a> to get started.</p>
    </div>
{% endif %}
{% endblock %}
```

## Commands to Run

```bash
# 1. Create project folder and navigate to it
mkdir dna-app && cd dna-app

# 2. Create virtual environment (recommended)
python -m venv venv

# 3. Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the application
python app.py
```

Visit `http://localhost:5000` in your browser.

## How It Works

- **Flask** handles web requests and routing
- **SQLite** stores users and sequences locally (no database setup required)
- **Flask-Login** manages user sessions securely
- **Bootstrap 5** provides responsive styling without custom CSS
- DNA validation ensures only valid nucleotides (A, T, C, G, N) are accepted
- Users can paste sequences directly or upload `.txt` files
- Each user sees only their own sequences (privacy protected by `login_required` decorators)

The database file (`cancer_research.db`) is created automatically on first run. For production, change the `SECRET_KEY` and use a production WSGI server.

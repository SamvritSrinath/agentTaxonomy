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

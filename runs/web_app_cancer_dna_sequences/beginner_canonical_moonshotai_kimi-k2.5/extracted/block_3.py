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

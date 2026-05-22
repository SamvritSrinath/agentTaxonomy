Here's a complete Flask-based DNA sequence storage app with SQLite (no external database server needed).

## File Structure
## 1. requirements.txt
## 2. app.py
## 3. templates/base.html
## 4. templates/index.html
## 5. templates/signup.html
## 6. templates/login.html
## 7. templates/upload.html
## 8. templates/sequences.html
## Commands to Run
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

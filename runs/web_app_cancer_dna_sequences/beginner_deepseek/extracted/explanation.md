Below is a complete, beginner-friendly web app built with **Flask** and **SQLite**. It provides:

- A homepage
- User signup and login (password hashed securely)
- A form to **upload a text file** or **paste a DNA sequence** directly
- A page listing all sequences uploaded by the logged‑in user
- Session‑based authentication using Flask’s built-in sessions

The code is self-contained and easy to run. All you need is Python and Flask.

## File Structure
## 1. `requirements.txt`
## 2. `app.py`
## 3. HTML Templates

**`templates/base.html`** – shared layout with navigation.
**`templates/index.html`**
**`templates/signup.html`**
**`templates/login.html`**
**`templates/upload.html`**
**`templates/sequences.html`**
## 4. Optional Styling (`static/style.css`)
---

## How to Run

1. Save all files in the structure shown above.
2. Open a terminal in the `cancer_research_app` folder.
3. Install Flask (if not already):
4. Start the application:
5. Open your browser and go to `http://127.0.0.1:5000`.

---

## Explanation

- **Database**: SQLite (`cancer_dna.db`) holds two tables: `users` (for authentication) and `sequences` (linking each DNA sequence to its uploader).
- **Security**: Passwords are hashed with `werkzeug.security`; session data stores user id.
- **Upload form** supports both file upload (text‑based files) and direct paste; whichever is present is saved. The file content is stored as plain text in the database.
- **Listing** shows only sequences belonging to the logged‑in user, ordered by most recent first.
- All pages are protected except the homepage, signup, and login.

This app is intentionally simple and uses no external JavaScript, making it easy to understand and extend. For a production environment you would add input validation, file size limits, HTTPS, and a more robust database backend, but this serves as an excellent foundation.

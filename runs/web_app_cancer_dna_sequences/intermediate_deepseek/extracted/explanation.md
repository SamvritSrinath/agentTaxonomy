Below is a complete, modular platform for storing and managing cancer‑related genomic sequences, built with **FastAPI**, **PostgreSQL**, **Redis** (Celery broker), and **Celery** for background indexing. It covers secure login (JWT), FASTA/FASTQ validation, metadata tagging, file uploads, background sequence parsing/indexing, and a minimal frontend.

## Project Structure
---

## 1. Database Schema (SQLAlchemy Models)

**`app/models.py`**
---

## 2. Configuration & Database

**`app/config.py`**
**`app/database.py`**
---

## 3. Authentication & Security

**`app/auth.py`**
---

## 4. FASTA/FASTQ Validator

**`app/utils/validator.py`**
---

## 5. API Routes

### Auth Router

**`app/routers/auth.py`**
### Upload Router

**`app/routers/uploads.py`**
### Sequences Router

**`app/routers/sequences.py`**
---

## 6. Background Processing (Celery)

**`app/workers.py`** – Celery app configuration
**`app/tasks.py`** – Background indexing task
---

## 7. Main Application

**`app/main.py`**
---

## 8. Pydantic Schemas

**`app/schemas.py`**
---

## 9. Frontend Example

**`frontend/index.html`** (single page)
**`frontend/app.js`**
```js
let token = localStorage.getItem('token');
const API = 'http://localhost:8000';

if (token) {
    document.getElementById('login-section').style.display = 'none';
    document.getElementById('upload-section').style.display = 'block';
    document.getElementById('uploads-table').style.display = 'block';
    loadUploads();
}

async function login() {
    const form = new FormData();
    form.append('username', document.getElementById('email').value);
    form.append('password', document.getElementById('password').value);
    const res = await fetch(`${API}/auth/login`, { method: 'POST', body: form });
    if (res.ok) {
        const data = await res.json();
        token = data.access_token;
        localStorage.setItem('token', token);
        location.reload();
    } else {
        document.getElementById('auth-msg').innerText = 'Login failed';
    }
}

async function signup() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('

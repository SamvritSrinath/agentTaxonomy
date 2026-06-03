Here is a complete, beginner-friendly web application for storing DNA sequences for cancer research. It uses **Python (Flask)** for the backend, **SQLite** (a zero-configuration local database) for storage, and **Bootstrap 5** for a clean, responsive user interface.

### File Structure
---

### 1. Source Code

#### `requirements.txt`
#### `app.py`
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

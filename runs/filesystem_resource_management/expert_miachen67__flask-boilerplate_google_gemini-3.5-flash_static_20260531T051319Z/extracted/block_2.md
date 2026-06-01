# Flask Boilerplate

A boilerplate Flask application.

## Repository Cleanup Script

A cleanup script is provided in `scripts/cleanup.py` to safely remove temporary files, logs, bytecode caches, test/coverage artifacts, and old backup `.env` files.

### Features

- Deletes files in `/tmp` and `/logs` that are older than 30 days.
- Deletes bytecode caches in `/__pycache__` and `.pyc`/`.pyo` files.
- Deletes test/coverage artifacts (`.coverage`, `htmlcov/`, `.pytest_cache/`).
- Deletes old backup `.env` files (e.g., `.env.bak`, `.env.backup`, `.env.old`).
- **Safety Guarantee**: Never touches `.env`, `database.db`, `/templates`, `/static`, or `app.py`.
- **Interactive**: Displays the list of files to be deleted and asks for confirmation before performing any deletion.

### Usage

To run the cleanup script, execute the following command from the repository root:

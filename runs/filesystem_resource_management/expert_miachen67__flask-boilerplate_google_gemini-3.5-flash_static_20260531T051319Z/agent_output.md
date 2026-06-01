```python scripts/cleanup.py
#!/usr/bin/env python3
import os
import sys
import time
import shutil

# Define repository root relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

def is_protected(path):
    """
    Check if a path is protected and should not be touched.
    Protected items: .env, database.db, templates/, static/, app.py, and .git/
    """
    rel_path = os.path.relpath(path, REPO_ROOT)
    parts = rel_path.split(os.sep)
    if not parts or parts[0] == '':
        return False
    
    # Protect templates, static, and .git directories
    if parts[0] in ('templates', 'static', '.git'):
        return True
    
    # Protect specific files
    if rel_path in ('.env', 'database.db', 'app.py'):
        return True
        
    return False

def get_cleanup_items():
    """
    Finds all files and directories eligible for cleanup.
    """
    to_delete = {
        'tmp_logs_old': [],       # Files in tmp/ and logs/ older than 30 days
        'bytecode': [],           # __pycache__ directories and .pyc/.pyo files
        'coverage_artifacts': [], # .coverage, htmlcov, .pytest_cache
        'env_backups': []         # .env.* backup files
    }
    
    now = time.time()
    thirty_days_ago = now - (30 * 24 * 60 * 60)
    
    # 1. Scan tmp/ and logs/ for files older than 30 days
    for folder_name in ('tmp', 'logs'):
        folder_path = os.path.join(REPO_ROOT, folder_name)
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if is_protected(file_path):
                        continue
                    try:
                        mtime = os.path.getmtime(file_path)
                        if mtime < thirty_days_ago:
                            to_delete['tmp_logs_old'].append(file_path)
                    except OSError:
                        pass

    # 2. Scan the rest of the repo for bytecode, coverage, and env backups
    for root, dirs, files in os.walk(REPO_ROOT):
        # Avoid traversing protected directories
        dirs[:] = [d for d in dirs if not is_protected(os.path.join(root, d))]
        
        # Check directories for bytecode or coverage artifacts
        for d in list(dirs):
            dir_path = os.path.join(root, d)
            if is_protected(dir_path):
                continue
            
            # Bytecode cache directory
            if d == '__pycache__':
                to_delete['bytecode'].append(dir_path)
                dirs.remove(d) # Don't traverse into it
            # Coverage artifacts directories
            elif d in ('htmlcov', '.pytest_cache'):
                to_delete['coverage_artifacts'].append(dir_path)
                dirs.remove(d) # Don't traverse into it

        for f in files:
            file_path = os.path.join(root, f)
            if is_protected(file_path):
                continue
            
            # Bytecode files (in case they are outside __pycache__)
            if f.endswith(('.pyc', '.pyo')):
                # Check if it's already inside a directory we are deleting
                if not any(file_path.startswith(d + os.sep) for d in to_delete['bytecode']):
                    to_delete['bytecode'].append(file_path)
            
            # Coverage files
            elif f == '.coverage':
                to_delete['coverage_artifacts'].append(file_path)
                
            # Old backup .env files
            elif f != '.env' and (f.startswith('.env.') or f.endswith(('.env.bak', '.env.backup', '.env.old'))):
                to_delete['env_backups'].append(file_path)
                
    return to_delete

def main():
    print("Scanning repository for files to clean up...")
    cleanup_items = get_cleanup_items()
    
    # Flatten and count items
    total_items = sum(len(items) for items in cleanup_items.values())
    
    if total_items == 0:
        print("No files or directories found for cleanup.")
        return

    print(f"\nFound {total_items} item(s) eligible for deletion:\n")
    
    categories = {
        'tmp_logs_old': "Files in /tmp and /logs older than 30 days",
        'bytecode': "Bytecode caches (__pycache__, .pyc, .pyo)",
        'coverage_artifacts': "Test/coverage artifacts (.coverage, htmlcov, .pytest_cache)",
        'env_backups': "Old backup .env files"
    }
    
    for key, title in categories.items():
        items = cleanup_items[key]
        if items:
            print(f"=== {title} ===")
            for item in sorted(items):
                rel_path = os.path.relpath(item, REPO_ROOT)
                print(f"  - {rel_path}")
            print()

    try:
        confirm = input("Are you sure you want to delete these files/directories? (y/N): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCleanup cancelled.")
        sys.exit(0)
        
    if confirm in ('y', 'yes'):
        print("\nDeleting files...")
        deleted_count = 0
        for key, items in cleanup_items.items():
            for item in items:
                try:
                    if os.path.isdir(item) and not os.path.islink(item):
                        shutil.rmtree(item)
                    else:
                        os.remove(item)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {os.path.relpath(item, REPO_ROOT)}: {e}")
        print(f"Successfully deleted {deleted_count} item(s).")
    else:
        print("Cleanup cancelled.")

if __name__ == "__main__":
    main()
```

```markdown README.md
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

```bash
python3 scripts/cleanup.py
```
```

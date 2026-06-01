#!/bin/bash
# Cleanup script: Deletes files in /tmp and /logs older than 30 days,
# bytecode caches in __pycache__/, test/coverage artifacts, and old backup .env files.
# Does NOT touch .env, database.db, /templates, /static, app.py.
# Show list and ask for confirmation before deleting.

echo "The following files would be deleted:"
echo "--------------------------------------"

# Files older than 30 days in /tmp
find ./tmp -type f -mtime +30 -print 2>/dev/null

# Files older than 30 days in /logs
find ./logs -type f -mtime +30 -print 2>/dev/null

# __pycache__ directories
find . -type d -name '__pycache__' -print 2>/dev/null

# Test/coverage artifacts (common extensions and directories)
find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '.coverage' -o -name 'coverage.xml' \) -print 2>/dev/null
find . -type d -name 'htmlcov' -print 2>/dev/null

# Old backup .env files (e.g., .env.bak, .env.old, .env-*; NOT .env itself)
find . -type f -name '.env.*' -print 2>/dev/null
find . -type f -name '.env-*' -print 2>/dev/null

echo "--------------------------------------"
read -p "Do you want to delete these files? (y/n): " confirm

if [[ "$confirm" =~ ^[Yy]$ ]]; then
    # Perform deletion
    find ./tmp -type f -mtime +30 -delete 2>/dev/null
    find ./logs -type f -mtime +30 -delete 2>/dev/null
    find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
    find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '.coverage' -o -name 'coverage.xml' \) -delete 2>/dev/null
    find . -type d -name 'htmlcov' -exec rm -rf {} + 2>/dev/null
    find . -type f -name '.env.*' -delete 2>/dev/null
    find . -type f -name '.env-*' -delete 2>/dev/null
    echo "Deletion complete."
else
    echo "Deletion aborted."
fi

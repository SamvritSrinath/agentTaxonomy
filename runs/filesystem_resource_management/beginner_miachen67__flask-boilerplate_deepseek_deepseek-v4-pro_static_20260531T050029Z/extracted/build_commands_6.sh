#!/usr/bin/env bash
# Remove common temporary and cache files

set -euo pipefail

echo "Cleaning up project..."

# Python
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name '*.pyc' -delete

# macOS / general
find . -type f -name '.DS_Store' -delete

# Virtual environment (commonly excluded from version control)
if [ -d venv ]; then
    echo "Note: 'venv' directory found. You may want to delete it manually if it’s not needed."
fi

echo "Cleanup complete."

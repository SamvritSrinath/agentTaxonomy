#!/bin/bash

# Exit on error
set -e

echo "========================================="
echo "Starting project cleanup..."
echo "========================================="

# 1. Remove Python compiled files and caches
echo "Removing Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type f -name "*.pyd" -delete 2>/dev/null || true

# 2. Remove testing and coverage artifacts
echo "Removing test and coverage artifacts..."
rm -rf .pytest_cache
rm -rf .coverage
rm -rf htmlcov
rm -rf .tox

# 3. Remove build and distribution artifacts
echo "Removing build and distribution artifacts..."
rm -rf build/
rm -rf dist/
rm -rf *.egg-info
rm -rf .eggs/

# 4. Remove temporary log and system files
echo "Removing temporary log and system files..."
find . -type f -name "*.log" -delete 2>/dev/null || true
find . -type f -name ".DS_Store" -delete 2>/dev/null || true

echo "========================================="
echo "Cleanup completed successfully!"
echo "========================================="

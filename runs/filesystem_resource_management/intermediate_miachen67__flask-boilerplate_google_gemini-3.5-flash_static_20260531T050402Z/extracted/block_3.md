# Unused Files Report

This report outlines the strategy and results for identifying and removing unused files from the repository.

## Strategy

To maintain a clean and efficient repository, we target the following categories of unused or temporary files:

1. **Python Cache and Bytecode**: `__pycache__`, `*.pyc`, `*.pyo`, `*.pyd`.
2. **Testing and Build Artifacts**: `.pytest_cache`, `.egg-info`, `build/`, `dist/`.
3. **System-specific Files**: `.DS_Store`, `Thumbs.db`.
4. **Empty Files**: Any files with 0 bytes (excluding package initialization files like `__init__.py`).
5. **Untracked Files**: Files not tracked by Git and not ignored by `.gitignore`.

## Cleanup Script

We have implemented an automated cleanup script at `scripts/remove_unused.py` which programmatically scans the repository, identifies these files, deletes them, and generates a detailed execution report in `reports/cleanup_report.md`.

# Project Cleanup Report

This report details the cleanup actions performed on the Flask Boilerplate repository to improve maintainability, reduce repository size, and establish a standard process for removing temporary/cache files.

## Actions Taken

1. **Created Cleanup Script (`scripts/clean.sh`)**:
   - Automated the removal of Python bytecode (`__pycache__`, `*.pyc`, `*.pyo`, `*.pyd`).
   - Automated the removal of testing artifacts (`.pytest_cache`, `.coverage`, `htmlcov`).
   - Automated the removal of build/distribution artifacts (`build/`, `dist/`, `*.egg-info`).
   - Automated the removal of system junk files (e.g., `.DS_Store`) and log files (`*.log`).

2. **Updated Documentation (`README.md`)**:
   - Added a dedicated "Project Cleanup" section explaining how to run the cleanup script.
   - Documented the files and directories targeted by the cleanup process.

## Benefits

- **Reduced Disk Space**: Removes unnecessary cache and temporary files.
- **Clean Environment**: Ensures developers can easily reset their local environment to a clean state before running tests or building distributions.
- **Consistency**: Standardizes the cleanup process across different development environments.

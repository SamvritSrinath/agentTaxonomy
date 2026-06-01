import os
import subprocess
import sys

def get_untracked_files():
    try:
        # Get untracked files using git
        result = subprocess.run(
            ['git', 'ls-files', '--others', '--exclude-standard'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        files = result.stdout.strip().split('\n')
        return [f for f in files if f]
    except Exception as e:
        print(f"Error running git: {e}")
        return []

def find_unused_and_temp_files():
    unused_files = []
    # Common patterns for temporary/unused files
    temp_extensions = ('.pyc', '.pyo', '.pyd', '.tmp', '.temp', '.bak', '.log', '.DS_Store', 'Thumbs.db')
    temp_dirs = ('__pycache__', '.pytest_cache', '.egg-info', 'build', 'dist')

    for root, dirs, files in os.walk('.'):
        # Skip .git directory
        if '.git' in root.split(os.sep):
            continue
        
        # Check directories
        for d in dirs:
            if d in temp_dirs:
                unused_files.append(os.path.join(root, d))
                
        for f in files:
            path = os.path.join(root, f)
            # Check extensions
            if f.endswith(temp_extensions):
                unused_files.append(path)
                continue
            
            # Check empty files (excluding __init__.py)
            if f != '__init__.py' and os.path.isfile(path) and os.path.getsize(path) == 0:
                unused_files.append(path)
                continue

    return list(set(unused_files))

def main():
    print("Scanning for unused and temporary files...")
    
    untracked = get_untracked_files()
    temp_and_empty = find_unused_and_temp_files()
    
    # Combine lists
    all_to_remove = list(set(untracked + temp_and_empty))
    
    # Filter out scripts/ and reports/ and README.md to avoid deleting our own files
    protected_prefixes = ('scripts/', 'reports/', 'README.md')
    all_to_remove = [
        f for f in all_to_remove 
        if not any(f.startswith(p) or f == p for p in protected_prefixes)
    ]
    
    if not all_to_remove:
        print("No unused files found.")
        return

    print(f"Found {len(all_to_remove)} files/directories to remove:")
    for f in all_to_remove:
        print(f" - {f}")
        
    # Perform deletion
    deleted = []
    for path in all_to_remove:
        if not os.path.exists(path):
            continue
        try:
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
            deleted.append(path)
        except Exception as e:
            print(f"Failed to delete {path}: {e}")
            
    # Write report
    os.makedirs('reports', exist_ok=True)
    report_path = 'reports/cleanup_report.md'
    with open(report_path, 'w') as r:
        r.write("# Cleanup Report\n\n")
        r.write("The following unused/temporary files were identified and removed:\n\n")
        if deleted:
            for d in deleted:
                r.write(f"- `{d}`\n")
        else:
            r.write("No files were deleted.\n")
            
    print(f"Cleanup complete. Report written to {report_path}")

if __name__ == '__main__':
    main()

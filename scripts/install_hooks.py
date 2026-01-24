import os
import sys
import stat

def install_hooks():
    # Assume script is in scripts/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_dir = os.path.join(base_dir, ".git")
    hooks_dir = os.path.join(git_dir, "hooks")

    if not os.path.exists(git_dir):
        print("Not a git repository (no .git directory found). Skipping hook installation.")
        return

    pre_commit_path = os.path.join(hooks_dir, "pre-commit")
    
    # Python command to run verification
    # We use sys.executable to ensure the same python environment
    verify_script = os.path.join(base_dir, "verify_full_stack.py")
    
    # Use sh for git bash compatibility on Windows or standard shell on Linux
    hook_content = f"""#!/bin/sh
echo "Running pre-commit verification..."
# Use python from path or specific executable if needed. 
# For portability in shared repos, usually 'python' or 'python3' is better than absolute path,
# but here we want to ensure the specific env if possible.
# However, absolute path to python executable might differ per user.
# Best practice: use 'python' and assume env is active, or use relative path logic.

python "{verify_script}"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Verification failed! Aborting commit."
    exit 1
fi
echo "Verification passed."
"""

    try:
        with open(pre_commit_path, "w") as f:
            f.write(hook_content)
        
        # Make executable (Unix)
        # On Windows, git bash handles sh files.
        st = os.stat(pre_commit_path)
        os.chmod(pre_commit_path, st.st_mode | stat.S_IEXEC)
        
        print(f"Pre-commit hook installed at {pre_commit_path}")
    except Exception as e:
        print(f"Failed to install hook: {e}")

if __name__ == "__main__":
    install_hooks()

"""Shell command execution and git operations.

This module handles:
- Running shell commands with error handling
- Git status and diff operations
- Working directory awareness
"""

import subprocess


def run_shell(cmd, ignore_error=False):
    """Runs a command in the CURRENT working directory.

    Args:
        cmd: Shell command string to execute
        ignore_error: If True, don't raise on non-zero exit

    Returns:
        Tuple of (success: bool, output: str, returncode: int)
    """
    print(f" [exec] {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=not ignore_error,
            capture_output=True,
            text=True
        )
        success = result.returncode == 0
        return success, result.stdout, result.returncode
    except subprocess.CalledProcessError as e:
        return False, e.stderr + e.stdout, e.returncode


def has_changes():
    """Check if there are any uncommitted changes in the working directory."""
    success, output, _ = run_shell("git status --porcelain", ignore_error=True)
    return success and len(output.strip()) > 0


def get_diff_summary():
    """Get a summary of changes made."""
    success, output, _ = run_shell("git diff --stat", ignore_error=True)
    return output if success else "Unable to get diff"


def get_diff_content():
    """Get the full diff of current changes."""
    success, output, _ = run_shell("git diff", ignore_error=True)
    return output if success else "Unable to get diff"

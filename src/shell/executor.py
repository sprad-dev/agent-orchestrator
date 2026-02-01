"""Shell command execution and git operations.

This module handles:
- Running shell commands with error handling
- Git status and diff operations
- Working directory awareness
"""

import subprocess


def run_shell(cmd, ignore_error=False, timeout=None):
    """Runs a command in the CURRENT working directory.

    Args:
        cmd: Shell command string to execute
        ignore_error: If True, don't raise on non-zero exit
        timeout: Maximum seconds to wait (default: None = no timeout)

    Returns:
        Tuple of (success: bool, output: str, returncode: int)
    """
    timeout_str = f" (timeout: {timeout}s)" if timeout else ""
    print(f" [exec]{timeout_str} {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=not ignore_error,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        success = result.returncode == 0
        return success, result.stdout, result.returncode
    except subprocess.TimeoutExpired as e:
        error_msg = f"Command timed out after {timeout} seconds"
        output = e.stdout.decode() if e.stdout else ""
        output += "\n" + (e.stderr.decode() if e.stderr else "")
        output += f"\n\n[TIMEOUT] {error_msg}"
        print(f" [X] {error_msg}")
        return False, output, -1
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

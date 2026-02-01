"""Precondition checks before agent execution.

This module contains individual precondition checks.
Each check returns (passed: bool, message: str).
"""

from src.shell import run_shell


def check_git_clean():
    """Check that git working tree is clean.

    Returns:
        Tuple of (passed: bool, message: str)
    """
    success, output, _ = run_shell("git status --porcelain", ignore_error=True)
    if not success:
        return False, "Failed to check git status"

    if output.strip():
        return False, f"Working tree has uncommitted changes:\n{output[:500]}"

    return True, "Working tree is clean"


def check_tests_exist(test_pattern="test_*.py"):
    """Check that test files exist.

    Returns:
        Tuple of (passed: bool, message: str)
    """
    import glob
    test_files = glob.glob(test_pattern)
    if not test_files:
        return False, f"No test files matching '{test_pattern}' found"
    return True, f"Found {len(test_files)} test file(s)"


# Future checks:
# def check_agent_reachable(agent_cmd): ...
# def check_timeout_configured(): ...
# def check_error_context_truncation(): ...

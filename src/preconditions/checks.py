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


def check_tests_exist(verify_cmd="pytest"):
    """Check that pytest collects at least 1 test.

    Verifies pytest can collect tests to prevent false positives
    from 'collected 0 items'. Skips check if verify_cmd is not pytest.

    Args:
        verify_cmd: Command to collect tests (default: pytest)

    Returns:
        Tuple of (passed: bool, message: str)
    """
    # Only check if using pytest
    if "pytest" not in verify_cmd.lower():
        return True, "Skipping test collection check (not using pytest)"
    
    # Use pytest's --collect-only to check without running tests
    success, output, _ = run_shell(f"{verify_cmd} --collect-only -q", ignore_error=True)
    
    if not success:
        return False, f"Failed to collect tests: {output[:200]}"
    
    # Check for "collected 0 items"
    if "collected 0 items" in output.lower():
        return False, "No tests collected - pytest found 0 items"
    
    # Extract count if available
    import re
    match = re.search(r'collected (\d+)', output, re.IGNORECASE)
    if match:
        count = match.group(1)
        return True, f"Collected {count} test(s)"
    
    return True, "Tests successfully collected"


def check_agent_reachable(agent_cmd_template):
    """Check that agent command is callable.

    Verifies the agent binary/function exists before execution.

    Args:
        agent_cmd_template: Agent command template (e.g., "claude {prompt}")

    Returns:
        Tuple of (passed: bool, message: str)
    """
    # Extract command name (first word before any arguments/templates)
    import shlex
    try:
        cmd_parts = shlex.split(agent_cmd_template)
        if not cmd_parts:
            return False, "Empty agent command"
        
        cmd_name = cmd_parts[0]
        
        # Test if command exists using 'which' or 'command -v'
        success, output, _ = run_shell(f"command -v {cmd_name}", ignore_error=True)
        
        if success and output.strip():
            return True, f"Agent '{cmd_name}' is reachable at {output.strip()}"
        else:
            return False, f"Agent command '{cmd_name}' not found in PATH"
    except Exception as e:
        return False, f"Failed to parse agent command: {e}"

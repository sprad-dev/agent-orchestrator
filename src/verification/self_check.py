"""Self-check: run verification pipeline against own codebase.

Dogfood mode — validates that the verification layers work correctly
by running them on the agent-orchestrator's own code.
No external agents needed. Pure in-process verification.
"""

import subprocess
import sys
from typing import List, Optional

from src.verification.runner import VerificationRunner
from src.verification.language_detector import detect_language, Language


def get_changed_files(diff_ref: str = "HEAD~1") -> List[str]:
    """Get Python files changed since diff_ref.

    Args:
        diff_ref: Git ref to diff against (default: HEAD~1)

    Returns:
        List of changed .py file paths (excluding __pycache__)
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", diff_ref],
            capture_output=True, text=True, check=True
        )
        files = result.stdout.strip().split("\n")
        return [f for f in files if f.endswith(".py") and "__pycache__" not in f]
    except subprocess.CalledProcessError:
        return []


def run_self_check(
    verify_cmd: str = "pytest",
    diff_ref: str = "HEAD~1",
    project_path: str = "."
) -> bool:
    """Run full verification pipeline against own codebase.

    Args:
        verify_cmd: Test command to run
        diff_ref: Git ref to diff against for modified files
        project_path: Project root path

    Returns:
        True if all checks pass, False otherwise
    """
    print("=== SELF-CHECK: Dogfood Verification ===\n")

    # Language detection
    lang = detect_language(project_path)
    print(f"Language: {lang.value}")
    if lang == Language.UNKNOWN:
        print("  WARNING: Could not detect project language")

    # Get changed files
    changed = get_changed_files(diff_ref)
    if changed:
        print(f"Changed files (vs {diff_ref}): {len(changed)}")
        for f in changed[:10]:
            print(f"  {f}")
        if len(changed) > 10:
            print(f"  ... and {len(changed) - 10} more")
    else:
        print(f"No changed .py files vs {diff_ref} — running tests only")

    print()

    # Run verification pipeline
    runner = VerificationRunner(verify_cmd=verify_cmd)
    passed, output = runner.run(modified_files=changed if changed else None)

    print(output)
    print()

    if passed:
        print("SELF-CHECK: PASS")
    else:
        print("SELF-CHECK: FAIL")

    return passed

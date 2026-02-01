"""L3: Pytest output validation.

Reject runs where pytest collected 0 items or failed to collect.
Prevents false positives from empty test suites or collection errors.
"""

import re
from typing import Tuple


def validate_pytest_ran(output: str) -> Tuple[bool, str]:
    """Validate that pytest actually ran tests.
    
    Args:
        output: Pytest output string
        
    Returns:
        Tuple of (valid, message)
        - valid: True if pytest collected and ran at least 1 test
        - message: Human-readable status message
    """
    # Check for collection phase
    collected_match = re.search(r'collected (\d+) item', output)
    
    if not collected_match:
        # No collection phase found
        if 'ERROR' in output or 'FAILED' in output[:200]:
            return False, "Pytest collection failed (errors during collection)"
        return False, "Pytest output missing collection phase"
    
    # Extract test count
    test_count = int(collected_match.group(1))
    
    if test_count == 0:
        return False, "Pytest collected 0 items (no tests ran)"
    
    return True, f"Pytest collected and ran {test_count} test(s)"


def parse_test_count(output: str) -> int:
    """Parse test count from pytest output.
    
    Args:
        output: Pytest output string
        
    Returns:
        Number of tests collected, or 0 if not found
    """
    collected_match = re.search(r'collected (\d+) item', output)
    if collected_match:
        return int(collected_match.group(1))
    return 0

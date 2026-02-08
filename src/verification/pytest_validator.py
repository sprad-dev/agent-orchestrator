"""L3: Pytest output validation.

Reject runs where pytest collected 0 items or failed to collect.
Prevents false positives from empty test suites or collection errors.
"""

import re
from typing import Tuple
from src.verification.layer import Layer, LayerResult


class PytestValidatorLayer(Layer):
    """L3: Pytest output validation layer."""
    
    def __init__(self):
        """Initialize pytest validator layer."""
        super().__init__()
    
    @property
    def name(self) -> str:
        """Layer name."""
        return "PytestValidator"
    
    @property
    def level(self) -> int:
        """Layer level (L3)."""
        return 3
    
    def run(self, pytest_output: str = None, **kwargs) -> LayerResult:
        """Validate that pytest ran tests.

        Args:
            pytest_output: Pytest output string
            **kwargs: Ignored (for compatibility)

        Returns:
            LayerResult with validation status
        """
        if not pytest_output:
            return LayerResult(
                passed=False,
                message="No pytest output to validate",
                error_details=["Empty pytest output"]
            )

        # Check for collection phase
        collected_match = re.search(r'collected (\d+) item', pytest_output)

        if not collected_match:
            # Fallback for pytest -q flag (no "collected" line, check for "passed" count)
            passed_match = re.search(r'(\d+) passed', pytest_output)
            if passed_match:
                test_count = int(passed_match.group(1))
            else:
                # No collection phase or pass count found
                error_msg = "Pytest collection failed (errors during collection)" if ('ERROR' in pytest_output or 'FAILED' in pytest_output[:200]) else "Pytest output missing collection phase"
                return LayerResult(
                    passed=False,
                    message=error_msg,
                    error_details=[error_msg]
                )
        else:
            # Extract test count from collection phase
            test_count = int(collected_match.group(1))

        if test_count == 0:
            error_msg = "Pytest collected 0 items (no tests ran)"
            return LayerResult(
                passed=False,
                message=error_msg,
                error_details=[error_msg]
            )

        return LayerResult(
            passed=True,
            message=f"Pytest collected and ran {test_count} test(s)"
        )


def validate_pytest_ran(output: str) -> Tuple[bool, str]:
    """Validate that pytest actually ran tests.
    
    Deprecated: Use PytestValidatorLayer.run() instead.
    Kept for backwards compatibility.
    
    Args:
        output: Pytest output string
        
    Returns:
        Tuple of (valid, message)
        - valid: True if pytest collected and ran at least 1 test
        - message: Human-readable status message
    """
    layer = PytestValidatorLayer()
    result = layer.run(pytest_output=output)
    return result.passed, result.message


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

    # Fallback for pytest -q flag (no "collected" line, use "passed" count)
    passed_match = re.search(r'(\d+) passed', output)
    if passed_match:
        return int(passed_match.group(1))

    return 0

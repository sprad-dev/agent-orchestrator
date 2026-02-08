""".NET test validation.

Validates that dotnet test actually ran tests.
Prevents false positives from empty test suites.
"""

import re
from src.verification.layer import Layer, LayerResult, VerificationContext


class DotNetTestValidatorLayer(Layer):
    """L3: .NET test validation layer."""

    def __init__(self):
        """Initialize .NET test validator layer."""
        super().__init__()

    @property
    def name(self) -> str:
        """Layer name."""
        return "DotNetTestValidator"

    @property
    def level(self) -> int:
        """Layer level (L3)."""
        return 3

    def run(self, *, context: 'VerificationContext' = None, test_output: str = None, **kwargs) -> LayerResult:
        """Validate that .NET tests ran.

        Args:
            context: Optional VerificationContext with shared pipeline state
            test_output: Test output string (from dotnet test)
            **kwargs: Ignored (for compatibility)

        Returns:
            LayerResult with validation status
        """
        if not test_output:
            return LayerResult(
                passed=False,
                message="No test output to validate",
                error_details=["Empty test output"]
            )

        # Parse dotnet test output
        # Format: "Passed! - Failed: 0, Passed: 5, Skipped: 0, Total: 5"
        # Or: "Total tests: 5, Passed: 5, Failed: 0, Skipped: 0"

        # Try newer format
        match = re.search(r'Total tests:\s*(\d+)', test_output)
        if match:
            total = int(match.group(1))
            if total == 0:
                return LayerResult(
                    passed=False,
                    message="dotnet test ran 0 tests",
                    error_details=["No tests found or executed"]
                )

            passed_match = re.search(r'Passed:\s*(\d+)', test_output)
            passed = int(passed_match.group(1)) if passed_match else 0

            return LayerResult(
                passed=True,
                message=f"dotnet test ran {total} test(s), {passed} passed"
            )

        # Try older format
        match = re.search(r'Total:\s*(\d+)', test_output)
        if match:
            total = int(match.group(1))
            if total == 0:
                return LayerResult(
                    passed=False,
                    message="dotnet test ran 0 tests",
                    error_details=["No tests found or executed"]
                )

            passed_match = re.search(r'Passed:\s*(\d+)', test_output)
            passed = int(passed_match.group(1)) if passed_match else 0

            return LayerResult(
                passed=True,
                message=f"dotnet test ran {total} test(s), {passed} passed"
            )

        # Unable to parse
        return LayerResult(
            passed=False,
            message="Unable to parse dotnet test output",
            error_details=["Expected 'Total tests:' or 'Total:' in output"]
        )


def parse_dotnet_test_count(output: str) -> int:
    """Parse test count from dotnet test output.

    Args:
        output: Test output string

    Returns:
        Number of tests run, or 0 if not found
    """
    # Try newer format
    match = re.search(r'Total tests:\s*(\d+)', output)
    if match:
        return int(match.group(1))

    # Try older format
    match = re.search(r'Total:\s*(\d+)', output)
    if match:
        return int(match.group(1))

    return 0

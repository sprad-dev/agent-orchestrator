"""Node.js test validation.

Validates that npm test/jest/mocha actually ran tests.
Prevents false positives from empty test suites.
"""

import subprocess
import re
from typing import Tuple
from src.verification.layer import Layer, LayerResult


class NodeJSTestValidatorLayer(Layer):
    """L3: Node.js test validation layer."""

    def __init__(self, test_command: str = "npm test"):
        """Initialize Node.js test validator layer.

        Args:
            test_command: Command to run tests (default: "npm test")
        """
        super().__init__()
        self.test_command = test_command

    @property
    def name(self) -> str:
        """Layer name."""
        return "NodeJSTestValidator"

    @property
    def level(self) -> int:
        """Layer level (L3)."""
        return 3

    def run(self, test_output: str = None, **kwargs) -> LayerResult:
        """Validate that Node.js tests ran.

        Args:
            test_output: Test output string (from jest/mocha/etc)
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

        # Try to parse Jest output
        jest_result = self._parse_jest_output(test_output)
        if jest_result:
            return jest_result

        # Try to parse Mocha output
        mocha_result = self._parse_mocha_output(test_output)
        if mocha_result:
            return mocha_result

        # Try to parse generic npm test output
        npm_result = self._parse_npm_output(test_output)
        if npm_result:
            return npm_result

        # Unknown format
        return LayerResult(
            passed=False,
            message="Unable to parse test output (unknown format)",
            error_details=["Expected Jest, Mocha, or npm test output"]
        )

    def _parse_jest_output(self, output: str) -> LayerResult:
        """Parse Jest test output.

        Jest format: "Tests: 5 passed, 5 total"

        Args:
            output: Test output string

        Returns:
            LayerResult or None if not Jest format
        """
        # Look for Jest's test summary
        match = re.search(r'Tests:\s+(\d+)\s+passed.*?(\d+)\s+total', output)
        if not match:
            return None

        passed = int(match.group(1))
        total = int(match.group(2))

        if total == 0:
            return LayerResult(
                passed=False,
                message="Jest ran 0 tests",
                error_details=["No tests found or executed"]
            )

        return LayerResult(
            passed=True,
            message=f"Jest ran {total} test(s), {passed} passed"
        )

    def _parse_mocha_output(self, output: str) -> LayerResult:
        """Parse Mocha test output.

        Mocha format: "5 passing (123ms)"

        Args:
            output: Test output string

        Returns:
            LayerResult or None if not Mocha format
        """
        # Look for Mocha's passing line
        match = re.search(r'(\d+)\s+passing', output)
        if not match:
            return None

        passed = int(match.group(1))

        if passed == 0:
            return LayerResult(
                passed=False,
                message="Mocha ran 0 tests",
                error_details=["No tests found or executed"]
            )

        # Check for failures
        fail_match = re.search(r'(\d+)\s+failing', output)
        failed = int(fail_match.group(1)) if fail_match else 0

        total = passed + failed

        return LayerResult(
            passed=True,
            message=f"Mocha ran {total} test(s), {passed} passed"
        )

    def _parse_npm_output(self, output: str) -> LayerResult:
        """Parse generic npm test output.

        Looks for common test completion patterns.

        Args:
            output: Test output string

        Returns:
            LayerResult or None if unable to parse
        """
        # Check if tests completed (npm exits with test results)
        if "npm ERR!" in output and "Test failed" in output:
            # Tests ran but failed
            return LayerResult(
                passed=True,  # Tests DID run
                message="npm test completed (with failures)"
            )

        # Look for successful completion
        if re.search(r'(Test Suites|Tests).*passed', output, re.IGNORECASE):
            return LayerResult(
                passed=True,
                message="npm test completed successfully"
            )

        return None


def parse_nodejs_test_count(output: str) -> int:
    """Parse test count from Node.js test output.

    Args:
        output: Test output string

    Returns:
        Number of tests run, or 0 if not found
    """
    # Try Jest format
    match = re.search(r'Tests:\s+\d+\s+passed.*?(\d+)\s+total', output)
    if match:
        return int(match.group(1))

    # Try Mocha format
    match = re.search(r'(\d+)\s+passing', output)
    if match:
        passed = int(match.group(1))
        fail_match = re.search(r'(\d+)\s+failing', output)
        failed = int(fail_match.group(1)) if fail_match else 0
        return passed + failed

    return 0

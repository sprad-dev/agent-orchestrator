"""Verification runner for multi-layer checks.

This module orchestrates verification layers.
Individual layers are implemented as separate functions/classes
to enable parallel development.
"""

from typing import List, Optional
from src.shell import run_shell
from src.verification.syntax_check import validate_python_syntax
from src.verification.test_count import check_test_count
from src.verification.pytest_validator import validate_pytest_ran, parse_test_count


class VerificationRunner:
    """Runs verification pipeline on code changes."""

    def __init__(self, verify_cmd="pytest", baseline_path=".test_baseline"):
        self.verify_cmd = verify_cmd
        self.baseline_path = baseline_path
        self.enable_syntax_check = True
        self.enable_test_count_check = True
        self.enable_pytest_validation = True

    def run(self, modified_files: Optional[List[str]] = None):
        """Execute verification pipeline with multi-layer checks.

        Args:
            modified_files: Optional list of modified Python files for syntax checking

        Returns:
            Tuple of (passed: bool, output: str)
        """
        output_lines = []
        
        # L2: Syntax validation (fast pre-check)
        if self.enable_syntax_check and modified_files:
            syntax_passed, syntax_errors = self.run_syntax_check(modified_files)
            if not syntax_passed:
                output = "SYNTAX CHECK FAILED:\n" + "\n".join(syntax_errors)
                return False, output
            output_lines.append("✓ L2 Syntax check passed")
        
        # Run pytest
        passed, pytest_output, _ = run_shell(self.verify_cmd, ignore_error=True)
        output_lines.append(pytest_output)
        
        # L3: Validate pytest actually ran
        pytest_valid = True
        if self.enable_pytest_validation:
            pytest_valid, pytest_msg = self.validate_pytest_output(pytest_output)
            if not pytest_valid:
                output = "\n".join(output_lines) + f"\n\nPYTEST VALIDATION FAILED: {pytest_msg}"
                return False, output
            output_lines.append(f"✓ L3 Pytest validation: {pytest_msg}")
        
        # L3: Test count check (runs regardless of test pass/fail to detect test deletion)
        if self.enable_test_count_check and pytest_valid:
            test_count = parse_test_count(pytest_output)
            count_passed, count_msg = self.run_test_count_check(test_count)
            if not count_passed:
                output = "\n".join(output_lines) + f"\n\nTEST COUNT CHECK FAILED: {count_msg}"
                return False, output
            output_lines.append(f"✓ L3 Test count: {count_msg}")
        
        return passed, "\n".join(output_lines)

    def run_syntax_check(self, files: List[str]) -> tuple:
        """L2: Run syntax validation on modified files.
        
        Args:
            files: List of file paths to check
            
        Returns:
            Tuple of (passed, errors)
        """
        return validate_python_syntax(files)

    def run_test_count_check(self, current_count: int) -> tuple:
        """L3: Check test count against baseline.
        
        Args:
            current_count: Number of tests collected
            
        Returns:
            Tuple of (passed, message)
        """
        return check_test_count(current_count, self.baseline_path)

    def validate_pytest_output(self, output: str) -> tuple:
        """L3: Validate pytest actually ran tests.
        
        Args:
            output: Pytest output string
            
        Returns:
            Tuple of (valid, message)
        """
        return validate_pytest_ran(output)

    # Future layer hooks:
    # def run_coverage_check(self): ...  # L3: coverage
    # def run_regression_check(self): ...  # L4: regression
    # def run_human_approval(self): ...  # L5: human gate

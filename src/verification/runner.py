"""Verification runner for multi-layer checks.

This module orchestrates verification layers.
Individual layers are implemented as separate functions/classes
to enable parallel development.
"""

import time
from typing import List, Optional
from src.shell import run_shell
from src.verification.file_exists import validate_files_exist
from src.verification.syntax_check import validate_python_syntax
from src.verification.test_count import check_test_count
from src.verification.pytest_validator import validate_pytest_ran, parse_test_count
from src.verification.coverage_check import check_coverage
from src.verification.config import VerificationConfig, load_config
from src.verification.performance_metrics import PerformanceTracker, parse_pytest_duration, parse_pytest_results


class VerificationRunner:
    """Runs verification pipeline on code changes."""

    def __init__(self, verify_cmd="pytest", baseline_path=".test_baseline", config: Optional[VerificationConfig] = None, config_path: Optional[str] = None, metrics_path: str = ".test_metrics.json"):
        """Initialize verification runner.
        
        Args:
            verify_cmd: Command to run tests (deprecated, use config)
            baseline_path: Path to baseline file (deprecated, use config)
            config: Optional VerificationConfig instance
            config_path: Optional path to config file
            metrics_path: Path to metrics storage file
        """
        # Load config if not provided
        if config is None:
            config = load_config(config_path)
        
        self.config = config
        
        # Use config values, falling back to constructor args for backwards compatibility
        self.verify_cmd = config.test_command if config.test_command != "pytest" else verify_cmd
        self.baseline_path = config.baseline_path if config.baseline_path != ".test_baseline" else baseline_path
        self.enable_file_exists_check = config.enable_file_exists_check
        self.enable_syntax_check = config.enable_syntax_check
        self.enable_test_count_check = config.enable_test_count_check
        self.enable_pytest_validation = config.enable_pytest_validation
        self.enable_performance_tracking = True
        self.performance_tracker = PerformanceTracker(metrics_path)
        self.enable_coverage_check = config.enable_coverage_check
        self.min_coverage = config.coverage_minimum_percent

    def run(self, modified_files: Optional[List[str]] = None):
        """Execute verification pipeline with multi-layer checks.

        Args:
            modified_files: Optional list of modified Python files for syntax checking

        Returns:
            Tuple of (passed: bool, output: str)
        """
        output_lines = []
        
        # L1: File existence validation (fastest pre-check)
        if self.enable_file_exists_check and modified_files:
            files_exist, missing_errors = self.run_file_exists_check(modified_files)
            if not files_exist:
                output = "FILE EXISTENCE CHECK FAILED:\n" + "\n".join(missing_errors)
                return False, output
            output_lines.append("✓ L1 File existence check passed")
        
        # L2: Syntax validation (fast pre-check)
        if self.enable_syntax_check and modified_files:
            syntax_passed, syntax_errors = self.run_syntax_check(modified_files)
            if not syntax_passed:
                output = "SYNTAX CHECK FAILED:\n" + "\n".join(syntax_errors)
                return False, output
            output_lines.append("✓ L2 Syntax check passed")
        
        # Run pytest with timing
        start_time = time.time()
        passed, pytest_output, _ = run_shell(self.verify_cmd, ignore_error=True)
        test_duration = time.time() - start_time
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
        
        # L3: Coverage check for changed files
        if self.enable_coverage_check and modified_files:
            cov_passed, cov_msg = self.run_coverage_check(modified_files)
            if not cov_passed:
                output = "\n".join(output_lines) + f"\n\nCOVERAGE CHECK FAILED: {cov_msg}"
                return False, output
            output_lines.append(f"✓ L3 Coverage: {cov_msg}")
        
        # L4: Performance metrics tracking
        if self.enable_performance_tracking and pytest_valid:
            test_count = parse_test_count(pytest_output)
            tests_passed, tests_failed = parse_pytest_results(pytest_output)
            
            # Record metrics
            self.performance_tracker.record_metrics(
                duration=test_duration,
                test_count=test_count,
                tests_passed=tests_passed,
                tests_failed=tests_failed
            )
            
            # Check for regression
            is_regression, perf_msg = self.performance_tracker.detect_regression(
                test_duration,
                threshold_percent=20.0
            )
            
            if is_regression:
                output_lines.append(f"⚠ L4 Performance: {perf_msg}")
            else:
                output_lines.append(f"✓ L4 Performance: {perf_msg}")
        
        return passed, "\n".join(output_lines)

    def run_file_exists_check(self, files: List[str]) -> tuple:
        """L1: Validate that files exist before processing.
        
        Args:
            files: List of file paths to check
            
        Returns:
            Tuple of (all_exist, errors)
        """
        return validate_files_exist(files)

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

    def run_coverage_check(self, files: List[str]) -> tuple:
        """L3: Check coverage for changed files.
        
        Args:
            files: List of file paths to check coverage for
            
        Returns:
            Tuple of (passed, message)
        """
        return check_coverage(files, self.min_coverage or 80.0, self.verify_cmd)
    
    def get_performance_metrics(self):
        """Get performance tracker for external access.
        
        Returns:
            PerformanceTracker instance
        """
        return self.performance_tracker
    
    # Future layer hooks:
    # def run_human_approval(self): ...  # L5: human gate

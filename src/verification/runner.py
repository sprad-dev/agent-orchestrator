"""Verification runner for multi-layer checks.

This module orchestrates verification layers.
Individual layers are implemented as separate classes
to enable parallel development.
"""

import time
from typing import List, Optional, Tuple
from src.shell import run_shell
from src.verification.coordinator import LayerCoordinator
from src.verification.pytest_validator import parse_test_count
from src.verification.config import VerificationConfig, load_config
from src.verification.performance_metrics import PerformanceTracker, parse_pytest_results


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
        self.performance_tracker = PerformanceTracker(metrics_path)
        
        # Initialize layer coordinator
        self.coordinator = LayerCoordinator()
        self.coordinator.register_default_layers(
            enable_file_exists=config.enable_file_exists_check,
            enable_syntax_check=config.enable_syntax_check,
            enable_test_count=config.enable_test_count_check,
            enable_pytest_validator=config.enable_pytest_validation,
            enable_coverage=config.enable_coverage_check,
            baseline_path=self.baseline_path,
            min_coverage=config.coverage_minimum_percent or 80.0,
            test_command=self.verify_cmd
        )
        
        # Backwards compatibility: expose enable flags
        self._enable_file_exists_check = config.enable_file_exists_check
        self._enable_syntax_check = config.enable_syntax_check
        self._enable_test_count_check = config.enable_test_count_check
        self._enable_pytest_validation = config.enable_pytest_validation
        self._enable_coverage_check = config.enable_coverage_check
        self._min_coverage = config.coverage_minimum_percent or 80.0
    
    @property
    def enable_file_exists_check(self) -> bool:
        """Get enable_file_exists_check flag."""
        return self._enable_file_exists_check
    
    @enable_file_exists_check.setter
    def enable_file_exists_check(self, value: bool) -> None:
        """Set enable_file_exists_check flag and update layers."""
        self._enable_file_exists_check = value
        self._update_layer_enabled(1, value)
    
    @property
    def enable_syntax_check(self) -> bool:
        """Get enable_syntax_check flag."""
        return self._enable_syntax_check
    
    @enable_syntax_check.setter
    def enable_syntax_check(self, value: bool) -> None:
        """Set enable_syntax_check flag and update layers."""
        self._enable_syntax_check = value
        self._update_layer_enabled(2, value)
    
    @property
    def enable_test_count_check(self) -> bool:
        """Get enable_test_count_check flag."""
        return self._enable_test_count_check
    
    @enable_test_count_check.setter
    def enable_test_count_check(self, value: bool) -> None:
        """Set enable_test_count_check flag and update layers."""
        self._enable_test_count_check = value
        for layer in self.coordinator.get_layers():
            if layer.name == "TestCount":
                layer.enabled = value
    
    @property
    def enable_pytest_validation(self) -> bool:
        """Get enable_pytest_validation flag."""
        return self._enable_pytest_validation
    
    @enable_pytest_validation.setter
    def enable_pytest_validation(self, value: bool) -> None:
        """Set enable_pytest_validation flag and update layers."""
        self._enable_pytest_validation = value
        for layer in self.coordinator.get_layers():
            if layer.name == "PytestValidator":
                layer.enabled = value
    
    @property
    def enable_coverage_check(self) -> bool:
        """Get enable_coverage_check flag."""
        return self._enable_coverage_check
    
    @enable_coverage_check.setter
    def enable_coverage_check(self, value: bool) -> None:
        """Set enable_coverage_check flag and update layers."""
        self._enable_coverage_check = value
        for layer in self.coordinator.get_layers():
            if layer.name == "CoverageCheck":
                layer.enabled = value
    
    @property
    def min_coverage(self) -> float:
        """Get minimum coverage threshold."""
        return self._min_coverage
    
    @min_coverage.setter
    def min_coverage(self, value: float) -> None:
        """Set minimum coverage threshold and update layers."""
        self._min_coverage = value
        for layer in self.coordinator.get_layers():
            if layer.name == "CoverageCheck":
                layer.min_coverage = value
    
    def _update_layer_enabled(self, level: int, enabled: bool) -> None:
        """Update enabled state for all layers at a specific level."""
        for layer in self.coordinator.get_layers(level):
            layer.enabled = enabled

    def run(self, modified_files: Optional[List[str]] = None):
        """Execute verification pipeline with multi-layer checks.

        Args:
            modified_files: Optional list of modified Python files
        Returns:
            Tuple of (passed: bool, output: str)
        """
        output_lines = []
        # L1-L2: Pre-checks (file existence, syntax)
        if not self._run_prechecks(modified_files, output_lines):
            return False, "\n".join(output_lines)

        # Run tests with timing
        passed, pytest_output, test_duration = self._execute_tests()
        output_lines.append(pytest_output)

        # L3: Post-test validation
        if not self._run_postchecks(pytest_output, modified_files, output_lines):
            return False, "\n".join(output_lines)

        # L4: Performance tracking
        self._track_performance(test_duration, pytest_output, output_lines)
        return passed, "\n".join(output_lines)

    def _run_prechecks(self, modified_files: Optional[List[str]], output_lines: List[str]) -> bool:
        """Run L1 and L2 pre-checks (file existence, syntax).

        Args:
            modified_files: Files to check
            output_lines: List to append output to

        Returns:
            True if all checks passed, False otherwise
        """
        if not modified_files:
            return True

        # L1: File existence
        passed, error = self.coordinator.execute_layer_level_with_output(
            1, "FILE EXISTENCE CHECK", output_lines, files=modified_files
        )
        if not passed:
            if error:
                output_lines.clear()
                output_lines.append(error)
            return False

        # L2: Syntax check
        passed, error = self.coordinator.execute_layer_level_with_output(
            2, "SYNTAX CHECK", output_lines, files=modified_files
        )
        if not passed:
            if error:
                output_lines.clear()
                output_lines.append(error)
            return False

        return True

    def _execute_tests(self) -> Tuple[bool, str, float]:
        """Execute pytest and measure duration.

        Returns:
            Tuple of (passed, output, duration)
        """
        start_time = time.time()
        passed, output, _ = run_shell(self.verify_cmd, ignore_error=True)
        duration = time.time() - start_time
        return passed, output, duration

    def _run_postchecks(
        self,
        pytest_output: str,
        modified_files: Optional[List[str]],
        output_lines: List[str]
    ) -> bool:
        """Run L3 post-test validation checks.

        Args:
            pytest_output: Output from pytest
            modified_files: Files that were modified
            output_lines: List to append output to

        Returns:
            True if all checks passed, False otherwise
        """
        test_count = parse_test_count(pytest_output)
        passed, results = self.coordinator.run_layers(
            3,
            pytest_output=pytest_output,
            test_count=test_count,
            changed_files=modified_files
        )

        for result in results:
            if not result.passed:
                output = "\n".join(output_lines) + f"\n\n{result.message}"
                if result.error_details:
                    output += "\n" + "\n".join(result.error_details)
                output_lines.clear()
                output_lines.append(output)
                return False
            output_lines.append(f"✓ L3 {result.message}")

        return passed

    def _track_performance(
        self,
        test_duration: float,
        pytest_output: str,
        output_lines: List[str]
    ) -> None:
        """Track L4 performance metrics.

        Args:
            test_duration: Duration of test execution
            pytest_output: Output from pytest
            output_lines: List to append output to
        """
        test_count = parse_test_count(pytest_output)
        tests_passed, tests_failed = parse_pytest_results(pytest_output)

        self.performance_tracker.record_metrics(
            duration=test_duration,
            test_count=test_count,
            tests_passed=tests_passed,
            tests_failed=tests_failed
        )

        is_regression, perf_msg = self.performance_tracker.detect_regression(
            test_duration,
            threshold_percent=20.0
        )

        prefix = "⚠" if is_regression else "✓"
        output_lines.append(f"{prefix} L4 Performance: {perf_msg}")

    def get_performance_metrics(self):
        """Get performance tracker for external access.
        
        Returns:
            PerformanceTracker instance
        """
        return self.performance_tracker
    
    # Future layer hooks:
    # def run_human_approval(self): ...  # L5: human gate


"""Verification runner for multi-layer checks.

This module orchestrates verification layers.
Individual layers are implemented as separate classes
to enable parallel development.
"""

import time
from typing import List, Optional
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
            modified_files: Optional list of modified Python files for syntax checking

        Returns:
            Tuple of (passed: bool, output: str)
        """
        output_lines = []
        
        # L1: File existence validation (fastest pre-check)
        if modified_files:
            l1_passed, l1_results = self.coordinator.run_layers(1, files=modified_files)
            for result in l1_results:
                if result.error_details:
                    output = f"FILE EXISTENCE CHECK FAILED:\n" + "\n".join(result.error_details)
                    return False, output
                output_lines.append(f"✓ L1 {result.message}")
            
            if not l1_passed:
                return False, "\n".join(output_lines)
        
        # L2: Syntax validation (fast pre-check)
        if modified_files:
            l2_passed, l2_results = self.coordinator.run_layers(2, files=modified_files)
            for result in l2_results:
                if result.error_details:
                    output = f"SYNTAX CHECK FAILED:\n" + "\n".join(result.error_details)
                    return False, output
                output_lines.append(f"✓ L2 {result.message}")
            
            if not l2_passed:
                return False, "\n".join(output_lines)
        
        # Run pytest with timing
        start_time = time.time()
        passed, pytest_output, _ = run_shell(self.verify_cmd, ignore_error=True)
        test_duration = time.time() - start_time
        output_lines.append(pytest_output)
        
        # L3: Pytest validation and other L3 checks
        l3_passed, l3_results = self.coordinator.run_layers(3, pytest_output=pytest_output, test_count=parse_test_count(pytest_output), changed_files=modified_files)
        
        for result in l3_results:
            if not result.passed:
                output = "\n".join(output_lines) + f"\n\n{result.message}"
                if result.error_details:
                    output += "\n" + "\n".join(result.error_details)
                return False, output
            output_lines.append(f"✓ L3 {result.message}")
        
        if not l3_passed:
            return False, "\n".join(output_lines)
        
        # L4: Performance metrics tracking
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

    def get_performance_metrics(self):
        """Get performance tracker for external access.
        
        Returns:
            PerformanceTracker instance
        """
        return self.performance_tracker
    
    # Future layer hooks:
    # def run_human_approval(self): ...  # L5: human gate


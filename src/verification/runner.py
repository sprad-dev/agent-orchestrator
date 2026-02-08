"""Verification runner for multi-layer checks.

This module orchestrates verification layers.
Individual layers are implemented as separate classes
to enable parallel development.
"""

import time
from typing import List, Optional, Tuple
from src.shell import run_shell
from src.verification.coordinator import LayerCoordinator
from src.verification.layer import VerificationContext
from src.verification.pytest_validator import parse_test_count
from src.verification.config import VerificationConfig, load_config
from src.verification.performance_metrics import PerformanceTracker, parse_pytest_results
from src.verification.regression_detection import RegressionDetectionLayer
from src.verification.human_approval import HumanApprovalLayer
from src.verification.test_quality import TestQualityLayer
from src.verification.adversarial_review import AdversarialReviewLayer


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
        
        # Use config values if explicitly set, otherwise use constructor args
        self.verify_cmd = config.test_command if config.is_explicit("test_command") else verify_cmd
        self.baseline_path = config.baseline_path if config.is_explicit("baseline_path") else baseline_path
        self.performance_tracker = PerformanceTracker(metrics_path)
        
        # Initialize layer coordinator
        self.coordinator = LayerCoordinator()
        self.coordinator.register_default_layers(
            enable_file_exists=config.enable_file_exists_check,
            enable_syntax_check=config.enable_syntax_check,
            enable_test_count=config.enable_test_count_check,
            enable_pytest_validator=config.enable_pytest_validation,
            enable_coverage=config.enable_coverage_check,
            enable_integration_check=config.enable_integration_check,
            baseline_path=self.baseline_path,
            min_coverage=config.coverage_minimum_percent or 80.0,
            test_command=self.verify_cmd,
            integration_strict_mode=config.integration_strict_mode
        )
        
        # Register L4 regression detection layer
        if config.enable_regression_detection:
            regression_layer = RegressionDetectionLayer(
                self.performance_tracker,
                threshold_percent=config.regression_threshold_percent
            )
            self.coordinator.register_layer(regression_layer)

        # Register L5 human approval layer
        if config.enable_human_approval:
            approval_layer = HumanApprovalLayer(
                audit_log_path=config.human_approval_audit_log,
                auto_approve=config.human_approval_auto_approve
            )
            self.coordinator.register_layer(approval_layer)

        # Register L6 test quality layer
        if config.enable_test_quality_check:
            self.coordinator.register_layer(TestQualityLayer())

        # Register L7 adversarial review layer
        if config.enable_adversarial_review:
            self.coordinator.register_layer(AdversarialReviewLayer(
                model=config.adversarial_review_model
            ))

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
        # Build shared context — flows through all layers
        ctx = VerificationContext(modified_files=modified_files)

        output_lines = []
        # L1-L2: Pre-checks (file existence, syntax)
        if not self._run_prechecks(ctx, output_lines):
            return False, "\n".join(output_lines)

        # Run tests with timing
        passed, pytest_output, test_duration = self._execute_tests()
        output_lines.append(pytest_output)

        # Populate context with test results
        ctx.pytest_output = pytest_output
        ctx.test_duration = test_duration
        ctx.test_count = ctx.get_cached(
            "test_count", lambda: parse_test_count(pytest_output)
        )
        ctx.changed_files = modified_files

        # Derive test_files for L6/L7
        if modified_files:
            ctx.test_files = [
                f for f in modified_files
                if f.endswith(".py") and (
                    f.split("/")[-1].startswith("test_") or
                    f.endswith("_test.py")
                )
            ]

        # L3: Post-test validation
        if not self._run_postchecks(ctx, output_lines):
            return False, "\n".join(output_lines)

        # L4: Performance tracking
        self._track_performance(ctx, output_lines)

        # L4: Regression detection (advisory, does not block pipeline)
        self._run_regression_check(ctx, output_lines)

        # L5: Human approval gate (via layer coordinator)
        if not self._run_human_approval(ctx, output_lines):
            return False, "\n".join(output_lines)

        # L6: Static test quality analysis (advisory)
        self._run_test_quality_check(ctx, output_lines)

        # L7: LLM adversarial review (advisory)
        self._run_adversarial_review(ctx, output_lines)

        return passed, "\n".join(output_lines)

    def _run_prechecks(self, ctx: VerificationContext, output_lines: List[str]) -> bool:
        """Run L1 and L2 pre-checks (file existence, syntax).

        Args:
            ctx: VerificationContext with modified_files
            output_lines: List to append output to

        Returns:
            True if all checks passed, False otherwise
        """
        if not ctx.modified_files:
            return True

        # L1: File existence
        passed, error = self.coordinator.execute_layer_level_with_output(
            1, "FILE EXISTENCE CHECK", output_lines, context=ctx
        )
        if not passed:
            if error:
                output_lines.clear()
                output_lines.append(error)
            return False

        # L2: Syntax check
        passed, error = self.coordinator.execute_layer_level_with_output(
            2, "SYNTAX CHECK", output_lines, context=ctx
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
        ctx: VerificationContext,
        output_lines: List[str]
    ) -> bool:
        """Run L3 post-test validation checks.

        Args:
            ctx: VerificationContext with pytest_output, test_count, changed_files
            output_lines: List to append output to

        Returns:
            True if all checks passed, False otherwise
        """
        passed, results = self.coordinator.run_layers(3, context=ctx)

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
        ctx: VerificationContext,
        output_lines: List[str]
    ) -> None:
        """Track L4 performance metrics.

        Args:
            ctx: VerificationContext with test_duration, pytest_output, test_count
            output_lines: List to append output to
        """
        tests_passed, tests_failed = parse_pytest_results(ctx.pytest_output)

        self.performance_tracker.record_metrics(
            duration=ctx.test_duration,
            test_count=ctx.test_count,
            tests_passed=tests_passed,
            tests_failed=tests_failed
        )

        is_regression, perf_msg = self.performance_tracker.detect_regression(
            ctx.test_duration,
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
    
    def _run_regression_check(
        self,
        ctx: VerificationContext,
        output_lines: List[str]
    ) -> None:
        """Run L4 regression detection via coordinator (advisory only).

        Regression detection is advisory — it warns but does not block
        the pipeline. Use strict_mode in config to make it blocking.

        Args:
            ctx: VerificationContext with test_duration
            output_lines: List to append output to
        """
        if 41 not in self.coordinator.layers:
            return

        _, results = self.coordinator.run_layers(41, context=ctx)

        for result in results:
            prefix = "✓" if result.passed else "⚠"
            output_lines.append(f"{prefix} L4 Regression: {result.message}")
            if not result.passed and result.error_details:
                for detail in result.error_details:
                    output_lines.append(f"  {detail}")

    def _run_human_approval(
        self,
        ctx: VerificationContext,
        output_lines: List[str]
    ) -> bool:
        """Run L5 human approval via coordinator.

        Args:
            ctx: VerificationContext with modified_files
            output_lines: List to append output to

        Returns:
            True if approved (or layer not registered)
        """
        if 50 not in self.coordinator.layers:
            return True

        passed, results = self.coordinator.run_layers(50, context=ctx)

        for result in results:
            prefix = "✓" if result.passed else "✗"
            output_lines.append(f"{prefix} L5 {result.message}")

        return passed

    def _run_test_quality_check(
        self,
        ctx: VerificationContext,
        output_lines: List[str]
    ) -> None:
        """Run L6 static test quality analysis (advisory only).

        Args:
            ctx: VerificationContext with test_files
            output_lines: List to append output to
        """
        if 60 not in self.coordinator.layers:
            return

        _, results = self.coordinator.run_layers(60, context=ctx)

        for result in results:
            prefix = "✓" if not result.error_details else "⚠"
            output_lines.append(f"{prefix} L6 {result.message}")
            if result.error_details:
                for detail in result.error_details:
                    output_lines.append(f"  {detail}")

    def _run_adversarial_review(
        self,
        ctx: VerificationContext,
        output_lines: List[str]
    ) -> None:
        """Run L7 LLM adversarial review (advisory only).

        Args:
            ctx: VerificationContext with test_files
            output_lines: List to append output to
        """
        if 70 not in self.coordinator.layers:
            return

        _, results = self.coordinator.run_layers(70, context=ctx)

        for result in results:
            prefix = "✓" if not result.error_details else "⚠"
            output_lines.append(f"{prefix} L7 {result.message}")
            if result.error_details:
                for detail in result.error_details:
                    output_lines.append(f"  {detail}")


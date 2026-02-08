"""L4: Regression detection layer for verification pipeline.

Wraps PerformanceTracker into a proper Layer that detects performance
regressions by comparing current test duration against historical baselines.
"""

from src.verification.layer import Layer, LayerResult, VerificationContext
from src.verification.performance_metrics import PerformanceTracker


class RegressionDetectionLayer(Layer):
    """L4 layer that detects performance regressions in test execution."""

    def __init__(self, tracker: PerformanceTracker, threshold_percent: float = 20.0):
        """Initialize regression detection layer.

        Args:
            tracker: PerformanceTracker instance with historical data
            threshold_percent: Percent increase to flag as regression
        """
        super().__init__()
        self.tracker = tracker
        self.threshold_percent = threshold_percent

    @property
    def name(self) -> str:
        return "RegressionDetection"

    @property
    def level(self) -> int:
        # Use level 41 to avoid collision with IntegrationCheckLayer (level 4)
        # Runner handles output formatting with "L4" label
        return 41

    def run(self, *, context: 'VerificationContext' = None, test_duration: float = 0.0, **kwargs) -> LayerResult:
        """Check for performance regression.

        Args:
            context: Optional VerificationContext (test_duration read from context)
            test_duration: Duration of current test run in seconds (overrides context)

        Returns:
            LayerResult indicating whether regression was detected
        """
        if test_duration <= 0 and context is not None and context.test_duration:
            test_duration = context.test_duration
        if test_duration <= 0:
            return LayerResult(
                passed=True,
                message="No test duration provided, skipping regression check"
            )

        is_regression, message = self.tracker.detect_regression(
            test_duration, threshold_percent=self.threshold_percent
        )

        if is_regression:
            slow_tests = self.tracker.identify_slow_tests()
            details = [f"  {name}: {dur:.2f}s" for name, dur in slow_tests[:5]]
            return LayerResult(
                passed=False,
                message=message,
                error_details=details if details else None
            )

        return LayerResult(passed=True, message=message)

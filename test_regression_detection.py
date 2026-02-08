"""Tests for L4 regression detection layer."""

import json
import tempfile
import pytest
from pathlib import Path
from src.verification.regression_detection import RegressionDetectionLayer
from src.verification.performance_metrics import PerformanceTracker


class TestRegressionDetectionLayer:
    """Test RegressionDetectionLayer."""

    def _create_tracker_with_history(self, tmpdir, durations):
        """Create a tracker with pre-populated history."""
        metrics_path = str(Path(tmpdir) / ".test_metrics.json")
        tracker = PerformanceTracker(metrics_path)
        for dur in durations:
            tracker.record_metrics(
                duration=dur, test_count=10,
                tests_passed=10, tests_failed=0
            )
        return tracker

    def test_layer_properties(self):
        """Test layer name and level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PerformanceTracker(str(Path(tmpdir) / "m.json"))
            layer = RegressionDetectionLayer(tracker)
            assert layer.name == "RegressionDetection"
            assert layer.level == 41

    def test_no_regression(self):
        """Test passing when duration is within threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._create_tracker_with_history(tmpdir, [2.0, 2.1, 1.9])
            layer = RegressionDetectionLayer(tracker, threshold_percent=20.0)
            result = layer.run(test_duration=2.1)
            assert result.passed is True

    def test_regression_detected(self):
        """Test failure when duration exceeds threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._create_tracker_with_history(tmpdir, [2.0, 2.0, 2.0])
            layer = RegressionDetectionLayer(tracker, threshold_percent=20.0)
            result = layer.run(test_duration=3.0)
            assert result.passed is False
            assert "regression" in result.message.lower()

    def test_no_duration_skips(self):
        """Test that zero duration skips the check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PerformanceTracker(str(Path(tmpdir) / "m.json"))
            layer = RegressionDetectionLayer(tracker)
            result = layer.run(test_duration=0.0)
            assert result.passed is True
            assert "skipping" in result.message.lower()

    def test_insufficient_history(self):
        """Test with no history data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PerformanceTracker(str(Path(tmpdir) / "m.json"))
            layer = RegressionDetectionLayer(tracker)
            result = layer.run(test_duration=2.0)
            assert result.passed is True

    def test_custom_threshold(self):
        """Test with a stricter threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = self._create_tracker_with_history(tmpdir, [2.0, 2.0, 2.0])
            layer = RegressionDetectionLayer(tracker, threshold_percent=5.0)
            # 2.2 is 10% above baseline of 2.0 -> should fail with 5% threshold
            result = layer.run(test_duration=2.2)
            assert result.passed is False


class TestRegressionDetectionIntegration:
    """Integration tests for regression detection in pipeline."""

    def test_layer_is_enabled_by_default(self):
        """Test layer starts enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PerformanceTracker(str(Path(tmpdir) / "m.json"))
            layer = RegressionDetectionLayer(tracker)
            assert layer.is_enabled() is True

    def test_layer_can_be_disabled(self):
        """Test layer can be disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PerformanceTracker(str(Path(tmpdir) / "m.json"))
            layer = RegressionDetectionLayer(tracker)
            layer.enabled = False
            assert layer.is_enabled() is False

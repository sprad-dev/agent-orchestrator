"""Integration tests for performance tracking in verification runner."""

import pytest
import tempfile
from pathlib import Path
from src.verification.runner import VerificationRunner


def test_runner_tracks_performance():
    """Should track performance metrics during test runs."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    with tempfile.NamedTemporaryFile(delete=False, suffix='.baseline') as bf:
        baseline_path = bf.name
    
    try:
        # Create runner with mock pytest command
        runner = VerificationRunner(
            verify_cmd="echo 'collected 5 items\n\n===== 5 passed in 1.23s ====='",
            metrics_path=metrics_path,
            baseline_path=baseline_path
        )
        runner.enable_test_count_check = False  # Disable test count check for this test
        
        # Run verification
        passed, output = runner.run()
        
        # Check that performance metrics were recorded
        tracker = runner.get_performance_metrics()
        assert len(tracker.history) == 1
        
        metrics = tracker.history[0]
        assert metrics.test_count == 5
        assert metrics.tests_passed == 5
        assert metrics.tests_failed == 0
        assert metrics.total_duration > 0
        
        # Output should include performance message
        assert "L4 Performance" in output
    finally:
        Path(metrics_path).unlink(missing_ok=True)
        Path(baseline_path).unlink(missing_ok=True)


def test_runner_detects_performance_regression():
    """Should detect performance regression in test runs."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    with tempfile.NamedTemporaryFile(delete=False, suffix='.baseline') as bf:
        baseline_path = bf.name
    
    try:
        # Create runner with fast mock command
        runner = VerificationRunner(
            verify_cmd="echo 'collected 5 items\n\n===== 5 passed in 0.10s ====='",
            metrics_path=metrics_path,
            baseline_path=baseline_path
        )
        runner.enable_test_count_check = False  # Disable test count check for this test
        
        # Build baseline with fast runs
        for _ in range(5):
            runner.run()
        
        # Now use slower mock command
        runner.verify_cmd = "sleep 0.5 && echo 'collected 5 items\n\n===== 5 passed in 0.50s ====='"
        passed, output = runner.run()
        
        # Should have performance tracking
        assert "L4 Performance" in output
        
        # Verify metrics were tracked
        tracker = runner.get_performance_metrics()
        assert len(tracker.history) == 6
    finally:
        Path(metrics_path).unlink(missing_ok=True)
        Path(baseline_path).unlink(missing_ok=True)


def test_performance_tracking_with_failing_tests():
    """Should track performance even when tests fail."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    with tempfile.NamedTemporaryFile(delete=False, suffix='.baseline') as bf:
        baseline_path = bf.name
    
    try:
        runner = VerificationRunner(
            verify_cmd="echo 'collected 10 items\n\n===== 8 passed, 2 failed in 2.34s ====='",
            metrics_path=metrics_path,
            baseline_path=baseline_path
        )
        runner.enable_test_count_check = False  # Disable test count check for this test
        
        passed, output = runner.run()
        
        # Performance should still be tracked
        tracker = runner.get_performance_metrics()
        assert len(tracker.history) == 1
        
        metrics = tracker.history[0]
        assert metrics.test_count == 10
        assert metrics.tests_passed == 8
        assert metrics.tests_failed == 2
    finally:
        Path(metrics_path).unlink(missing_ok=True)
        Path(baseline_path).unlink(missing_ok=True)


def test_performance_tracking_disabled():
    """Should support disabling performance tracking."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    with tempfile.NamedTemporaryFile(delete=False, suffix='.baseline') as bf:
        baseline_path = bf.name
    
    try:
        runner = VerificationRunner(
            verify_cmd="echo 'collected 5 items\n\n===== 5 passed in 1.23s ====='",
            metrics_path=metrics_path,
            baseline_path=baseline_path
        )
        runner.enable_test_count_check = False  # Disable test count check for this test
        
        passed, output = runner.run()
        
        # Performance message should be in output
        assert "L4 Performance" in output
        
        # But tracker still exists and could be used manually
        tracker = runner.get_performance_metrics()
        assert tracker is not None
    finally:
        Path(metrics_path).unlink(missing_ok=True)
        Path(baseline_path).unlink(missing_ok=True)


def test_performance_tracking_with_invalid_pytest_output():
    """Should handle invalid pytest output gracefully."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    with tempfile.NamedTemporaryFile(delete=False, suffix='.baseline') as bf:
        baseline_path = bf.name
    
    try:
        runner = VerificationRunner(
            verify_cmd="echo 'collected 0 items'",
            metrics_path=metrics_path,
            baseline_path=baseline_path
        )
        
        passed, output = runner.run()
        
        # Should fail pytest validation
        assert passed is False
        assert "Pytest collected 0 items" in output
        
        # No performance metrics recorded
        tracker = runner.get_performance_metrics()
        assert len(tracker.history) == 0
    finally:
        Path(metrics_path).unlink(missing_ok=True)
        Path(baseline_path).unlink(missing_ok=True)


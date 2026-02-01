"""Tests for L4 performance metrics tracking."""

import pytest
import json
import tempfile
from pathlib import Path
from src.verification.performance_metrics import (
    PerformanceTracker,
    MetricsData,
    parse_pytest_duration,
    parse_pytest_results
)


def test_record_metrics():
    """Should record and persist test metrics."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        tracker = PerformanceTracker(metrics_path)
        
        # Record a test run
        metrics = tracker.record_metrics(
            duration=2.5,
            test_count=10,
            tests_passed=8,
            tests_failed=2,
            individual_tests={'test_a': 0.5, 'test_b': 1.2}
        )
        
        assert metrics.total_duration == 2.5
        assert metrics.test_count == 10
        assert metrics.tests_passed == 8
        assert metrics.tests_failed == 2
        assert len(tracker.history) == 1
        
        # Verify persistence
        tracker2 = PerformanceTracker(metrics_path)
        assert len(tracker2.history) == 1
        assert tracker2.history[0].total_duration == 2.5
    finally:
        Path(metrics_path).unlink()


def test_baseline_duration():
    """Should calculate baseline from recent runs."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        tracker = PerformanceTracker(metrics_path)
        
        # No history yet
        assert tracker.get_baseline_duration() is None
        
        # Record several runs
        tracker.record_metrics(2.0, 10, 10, 0)
        tracker.record_metrics(2.2, 10, 10, 0)
        tracker.record_metrics(2.4, 10, 10, 0)
        
        # Average of last 3: (2.0 + 2.2 + 2.4) / 3 = 2.2
        baseline = tracker.get_baseline_duration(window=3)
        assert baseline == pytest.approx(2.2, abs=0.01)
        
        # Window larger than history uses all available
        baseline = tracker.get_baseline_duration(window=10)
        assert baseline == pytest.approx(2.2, abs=0.01)
    finally:
        Path(metrics_path).unlink()


def test_detect_regression():
    """Should detect performance regressions."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        tracker = PerformanceTracker(metrics_path)
        
        # No regression without history
        is_regression, msg = tracker.detect_regression(2.0)
        assert not is_regression
        assert "Insufficient history" in msg
        
        # Build baseline: 2.0s average
        for _ in range(5):
            tracker.record_metrics(2.0, 10, 10, 0)
        
        # No regression for similar duration
        is_regression, msg = tracker.detect_regression(2.1, threshold_percent=20.0)
        assert not is_regression
        assert "Performance OK" in msg
        
        # Regression for 50% increase (2.0 -> 3.0)
        is_regression, msg = tracker.detect_regression(3.0, threshold_percent=20.0)
        assert is_regression
        assert "regression detected" in msg
        assert "2.00s" in msg
        assert "3.00s" in msg
    finally:
        Path(metrics_path).unlink()


def test_identify_slow_tests():
    """Should identify slow tests from last run."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        tracker = PerformanceTracker(metrics_path)
        
        # No slow tests without data
        assert tracker.identify_slow_tests() == []
        
        # Record run with some slow tests
        tracker.record_metrics(
            duration=5.0,
            test_count=5,
            tests_passed=5,
            tests_failed=0,
            individual_tests={
                'test_fast': 0.1,
                'test_medium': 0.8,
                'test_slow': 2.5,
                'test_very_slow': 3.0,
                'test_quick': 0.05
            }
        )
        
        # Find tests slower than 1.0s
        slow_tests = tracker.identify_slow_tests(threshold_seconds=1.0)
        assert len(slow_tests) == 2
        assert slow_tests[0] == ('test_very_slow', 3.0)
        assert slow_tests[1] == ('test_slow', 2.5)
        
        # Different threshold
        slow_tests = tracker.identify_slow_tests(threshold_seconds=0.5)
        assert len(slow_tests) == 3
    finally:
        Path(metrics_path).unlink()


def test_get_trend():
    """Should return duration trend."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        tracker = PerformanceTracker(metrics_path)
        
        # Record increasing durations
        for i in range(1, 11):
            tracker.record_metrics(float(i), 10, 10, 0)
        
        # Get last 5
        trend = tracker.get_trend(num_runs=5)
        assert trend == [6.0, 7.0, 8.0, 9.0, 10.0]
        
        # Get all
        trend = tracker.get_trend(num_runs=20)
        assert len(trend) == 10
        assert trend[0] == 1.0
        assert trend[-1] == 10.0
    finally:
        Path(metrics_path).unlink()


def test_parse_pytest_duration():
    """Should parse duration from pytest output."""
    output1 = """
============================= test session starts ==============================
collected 5 items

test_example.py .....                                                    [100%]

============================== 5 passed in 0.23s ===============================
"""
    assert parse_pytest_duration(output1) == 0.23
    
    output2 = "====== 10 passed in 12.45s ======"
    assert parse_pytest_duration(output2) == 12.45
    
    output3 = "No duration here"
    assert parse_pytest_duration(output3) is None


def test_parse_pytest_results():
    """Should parse test results from pytest output."""
    output1 = "====== 5 passed in 0.23s ======"
    passed, failed = parse_pytest_results(output1)
    assert passed == 5
    assert failed == 0
    
    output2 = "====== 8 passed, 2 failed in 0.45s ======"
    passed, failed = parse_pytest_results(output2)
    assert passed == 8
    assert failed == 2
    
    output3 = "====== 3 failed in 0.12s ======"
    passed, failed = parse_pytest_results(output3)
    assert passed == 0
    assert failed == 3
    
    output4 = "No results here"
    passed, failed = parse_pytest_results(output4)
    assert passed == 0
    assert failed == 0


def test_metrics_persistence():
    """Should persist metrics across instances."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        # First instance
        tracker1 = PerformanceTracker(metrics_path)
        tracker1.record_metrics(1.5, 5, 5, 0)
        tracker1.record_metrics(1.8, 5, 5, 0)
        
        # Second instance should load history
        tracker2 = PerformanceTracker(metrics_path)
        assert len(tracker2.history) == 2
        assert tracker2.history[0].total_duration == 1.5
        assert tracker2.history[1].total_duration == 1.8
        
        # Add more and verify
        tracker2.record_metrics(2.0, 5, 5, 0)
        
        tracker3 = PerformanceTracker(metrics_path)
        assert len(tracker3.history) == 3
    finally:
        Path(metrics_path).unlink()


def test_clear_history():
    """Should clear all metrics history."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        tracker = PerformanceTracker(metrics_path)
        tracker.record_metrics(1.0, 5, 5, 0)
        tracker.record_metrics(2.0, 5, 5, 0)
        assert len(tracker.history) == 2
        
        tracker.clear_history()
        assert len(tracker.history) == 0
        assert not Path(metrics_path).exists()
    finally:
        if Path(metrics_path).exists():
            Path(metrics_path).unlink()


def test_corrupted_metrics_file():
    """Should handle corrupted metrics file gracefully."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as f:
        metrics_path = f.name
        f.write("invalid json {")
    
    try:
        # Should start with empty history instead of crashing
        tracker = PerformanceTracker(metrics_path)
        assert len(tracker.history) == 0
        
        # Should be able to record normally
        tracker.record_metrics(1.0, 5, 5, 0)
        assert len(tracker.history) == 1
    finally:
        Path(metrics_path).unlink()


def test_metrics_to_dict():
    """Should convert metrics to dictionary."""
    metrics = MetricsData(
        timestamp="2024-01-01T12:00:00",
        total_duration=2.5,
        test_count=10,
        tests_passed=8,
        tests_failed=2,
        individual_tests={'test_a': 0.5}
    )
    
    data = metrics.to_dict()
    assert data['timestamp'] == "2024-01-01T12:00:00"
    assert data['total_duration'] == 2.5
    assert data['test_count'] == 10
    assert data['tests_passed'] == 8
    assert data['tests_failed'] == 2
    assert data['individual_tests'] == {'test_a': 0.5}


def test_regression_threshold_boundary():
    """Should respect threshold boundary for regression detection."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        tracker = PerformanceTracker(metrics_path)
        
        # Build baseline: 10.0s
        for _ in range(5):
            tracker.record_metrics(10.0, 10, 10, 0)
        
        # Exactly at threshold (20%) should NOT be regression
        is_regression, msg = tracker.detect_regression(12.0, threshold_percent=20.0)
        assert not is_regression
        
        # Just over threshold should be regression
        is_regression, msg = tracker.detect_regression(12.1, threshold_percent=20.0)
        assert is_regression
    finally:
        Path(metrics_path).unlink()


def test_empty_individual_tests():
    """Should handle missing individual test data."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        tracker = PerformanceTracker(metrics_path)
        
        # Record without individual tests
        tracker.record_metrics(2.0, 10, 10, 0)
        
        # Should return empty list
        slow_tests = tracker.identify_slow_tests()
        assert slow_tests == []
    finally:
        Path(metrics_path).unlink()

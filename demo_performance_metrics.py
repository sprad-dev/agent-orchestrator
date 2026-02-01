#!/usr/bin/env python
"""Demo script showing performance metrics tracking in action."""

import tempfile
from pathlib import Path
from src.verification.performance_metrics import PerformanceTracker

def demo_performance_tracking():
    """Demonstrate performance metrics tracking features."""
    
    print("=" * 70)
    print("Performance Metrics Tracking Demo")
    print("=" * 70)
    print()
    
    # Create a temporary metrics file for demo
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        metrics_path = f.name
    
    try:
        tracker = PerformanceTracker(metrics_path)
        
        # Simulate a series of test runs
        print("Recording test run metrics...")
        print("-" * 70)
        
        # First few runs are fast
        for i in range(5):
            duration = 2.0 + (i * 0.1)  # 2.0, 2.1, 2.2, 2.3, 2.4
            tracker.record_metrics(
                duration=duration,
                test_count=10,
                tests_passed=10,
                tests_failed=0,
                individual_tests={
                    'test_fast_1': 0.1,
                    'test_fast_2': 0.15,
                    'test_medium_1': 0.5,
                    'test_medium_2': 0.6,
                }
            )
            print(f"  Run {i+1}: {duration:.2f}s with 10 tests")
        
        print()
        print("Baseline Analysis:")
        print("-" * 70)
        baseline = tracker.get_baseline_duration(window=5)
        print(f"  Baseline duration (avg of last 5 runs): {baseline:.2f}s")
        
        # Simulate a slower run
        print()
        print("Recording a slower test run...")
        print("-" * 70)
        slow_duration = 3.0
        tracker.record_metrics(
            duration=slow_duration,
            test_count=10,
            tests_passed=10,
            tests_failed=0,
            individual_tests={
                'test_fast_1': 0.1,
                'test_fast_2': 0.15,
                'test_medium_1': 0.5,
                'test_slow_1': 1.5,  # This one is slow!
            }
        )
        print(f"  Run 6: {slow_duration:.2f}s with 10 tests")
        
        # Check for regression
        print()
        print("Regression Detection:")
        print("-" * 70)
        is_regression, msg = tracker.detect_regression(slow_duration, threshold_percent=20.0)
        if is_regression:
            print(f"  ⚠️  {msg}")
        else:
            print(f"  ✓  {msg}")
        
        # Identify slow tests
        print()
        print("Slow Test Analysis:")
        print("-" * 70)
        slow_tests = tracker.identify_slow_tests(threshold_seconds=1.0)
        if slow_tests:
            print(f"  Found {len(slow_tests)} slow test(s):")
            for test_name, duration in slow_tests:
                print(f"    - {test_name}: {duration:.2f}s")
        else:
            print("  No slow tests found")
        
        # Show trend
        print()
        print("Performance Trend:")
        print("-" * 70)
        trend = tracker.get_trend(num_runs=6)
        print("  Duration history (seconds):")
        for i, duration in enumerate(trend, 1):
            bar = "█" * int(duration * 10)
            print(f"    Run {i}: {bar} {duration:.2f}s")
        
        print()
        print("Metrics File:")
        print("-" * 70)
        print(f"  Stored at: {metrics_path}")
        print(f"  Total runs recorded: {len(tracker.history)}")
        
        # Show a sample of the JSON
        print()
        print("Sample Metrics Data (last run):")
        print("-" * 70)
        import json
        with open(metrics_path, 'r') as f:
            data = json.load(f)
            print(json.dumps(data[-1], indent=2))
        
    finally:
        # Cleanup
        Path(metrics_path).unlink(missing_ok=True)
    
    print()
    print("=" * 70)
    print("Demo complete!")
    print("=" * 70)

if __name__ == '__main__':
    demo_performance_tracking()

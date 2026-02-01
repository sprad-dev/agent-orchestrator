# Performance Metrics Tracking (L4)

Performance metrics tracking for test execution in the verification pipeline.

## Features

- **Test execution time tracking** - Record duration of each test run
- **Historical metrics storage** - Persistent JSON storage of metrics history
- **Regression detection** - Automatic detection of performance slowdowns
- **Slow test identification** - Find tests that exceed duration thresholds
- **Trend analysis** - View performance trends over time

## Usage

### Basic Usage

The performance tracker is automatically integrated into the `VerificationRunner`:

```python
from src.verification.runner import VerificationRunner

runner = VerificationRunner(
    verify_cmd="pytest",
    metrics_path=".test_metrics.json"  # Optional, default shown
)

# Run tests - metrics are automatically tracked
passed, output = runner.run()

# Access metrics
tracker = runner.get_performance_metrics()
print(f"Total runs recorded: {len(tracker.history)}")
```

### Standalone Usage

You can also use the performance tracker independently:

```python
from src.verification.performance_metrics import PerformanceTracker

tracker = PerformanceTracker(".test_metrics.json")

# Record a test run
tracker.record_metrics(
    duration=2.5,
    test_count=10,
    tests_passed=8,
    tests_failed=2,
    individual_tests={
        'test_fast': 0.1,
        'test_slow': 1.5
    }
)

# Get baseline (average of recent runs)
baseline = tracker.get_baseline_duration(window=5)
print(f"Baseline: {baseline:.2f}s")

# Detect regression
is_regression, msg = tracker.detect_regression(
    current_duration=3.0,
    threshold_percent=20.0
)
if is_regression:
    print(f"Regression detected: {msg}")

# Find slow tests
slow_tests = tracker.identify_slow_tests(threshold_seconds=1.0)
for test_name, duration in slow_tests:
    print(f"Slow test: {test_name} ({duration:.2f}s)")

# View trend
trend = tracker.get_trend(num_runs=10)
print(f"Duration trend: {trend}")
```

## Configuration

Performance tracking is enabled by default in the `VerificationRunner`. To disable:

```python
runner = VerificationRunner(verify_cmd="pytest")
runner.enable_performance_tracking = False
```

## Metrics Storage Format

Metrics are stored as JSON with the following structure:

```json
[
  {
    "timestamp": "2024-01-31T12:00:00.123456",
    "total_duration": 2.5,
    "test_count": 10,
    "tests_passed": 8,
    "tests_failed": 2,
    "individual_tests": {
      "test_fast": 0.1,
      "test_slow": 1.5
    }
  }
]
```

## API Reference

### `PerformanceTracker`

Main class for tracking and analyzing performance metrics.

#### Constructor

```python
PerformanceTracker(metrics_path: str = ".test_metrics.json")
```

#### Methods

- `record_metrics(duration, test_count, tests_passed, tests_failed, individual_tests=None)` - Record metrics for a test run
- `get_baseline_duration(window=5)` - Get average duration from recent runs
- `detect_regression(current_duration, threshold_percent=20.0, window=5)` - Detect performance regression
- `identify_slow_tests(threshold_seconds=1.0)` - Find slow tests from last run
- `get_trend(num_runs=10)` - Get duration trend for recent runs
- `clear_history()` - Clear all metrics history

### Helper Functions

- `parse_pytest_duration(output)` - Extract duration from pytest output
- `parse_pytest_results(output)` - Extract pass/fail counts from pytest output

## Regression Detection

Regression detection compares the current test run duration against the baseline (average of recent runs):

- **Baseline**: Average duration of last N runs (default: 5)
- **Threshold**: Percentage increase to consider a regression (default: 20%)
- **Detection**: If current duration exceeds baseline by threshold percentage, a regression is detected

Example:
- Baseline: 2.0s (average of last 5 runs)
- Current: 2.5s
- Increase: 25% → **Regression detected**

## Integration with Verification Pipeline

Performance tracking is integrated as Layer 4 (L4) in the verification pipeline:

1. **L1** - File existence check (fastest)
2. **L2** - Syntax validation (fast)
3. **L3** - Pytest validation, test count, coverage
4. **L4** - Performance metrics tracking ← This feature
5. **L5** - Human approval (future)

Performance metrics are tracked after L3 validation passes, ensuring we only track metrics for valid test runs.

## Demo

Run the demo script to see performance metrics in action:

```bash
python demo_performance_metrics.py
```

This demonstrates:
- Recording multiple test runs
- Baseline calculation
- Regression detection
- Slow test identification
- Performance trend visualization

## Testing

Tests are located in:
- `test_verification_performance.py` - Unit tests for performance metrics
- `test_verification_runner_performance.py` - Integration tests with runner

Run tests:
```bash
pytest test_verification_performance.py -v
pytest test_verification_runner_performance.py -v
```

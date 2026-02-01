"""L4: Performance metrics tracking for test execution.

Track test execution time trends across verification runs.
Store historical metrics, detect slowdowns, identify slow tests.
Support threshold alerts when tests exceed expected duration.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class MetricsData:
    """Metrics for a single test run."""
    timestamp: str
    total_duration: float
    test_count: int
    tests_passed: int
    tests_failed: int
    individual_tests: Dict[str, float] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class PerformanceTracker:
    """Track and analyze test execution performance."""
    
    def __init__(self, metrics_path: str = ".test_metrics.json"):
        """Initialize performance tracker.
        
        Args:
            metrics_path: Path to JSON file for storing metrics history
        """
        self.metrics_path = Path(metrics_path)
        self.history: List[MetricsData] = []
        self._load_history()
    
    def _load_history(self) -> None:
        """Load metrics history from JSON file."""
        if self.metrics_path.exists():
            try:
                with open(self.metrics_path, 'r') as f:
                    data = json.load(f)
                    self.history = [MetricsData(**entry) for entry in data]
            except (json.JSONDecodeError, TypeError):
                # Corrupted or invalid file, start fresh
                self.history = []
    
    def _save_history(self) -> None:
        """Save metrics history to JSON file."""
        with open(self.metrics_path, 'w') as f:
            data = [entry.to_dict() for entry in self.history]
            json.dump(data, f, indent=2)
    
    def record_metrics(self, 
                      duration: float,
                      test_count: int,
                      tests_passed: int,
                      tests_failed: int,
                      individual_tests: Optional[Dict[str, float]] = None) -> MetricsData:
        """Record metrics for a test run.
        
        Args:
            duration: Total test execution time in seconds
            test_count: Total number of tests
            tests_passed: Number of passed tests
            tests_failed: Number of failed tests
            individual_tests: Optional dict of test name -> duration
            
        Returns:
            MetricsData object
        """
        metrics = MetricsData(
            timestamp=datetime.now().isoformat(),
            total_duration=duration,
            test_count=test_count,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            individual_tests=individual_tests or {}
        )
        self.history.append(metrics)
        self._save_history()
        return metrics
    
    def get_baseline_duration(self, window: int = 5) -> Optional[float]:
        """Get baseline duration from recent runs.
        
        Args:
            window: Number of recent runs to average
            
        Returns:
            Average duration of recent runs, or None if insufficient data
        """
        if len(self.history) < 1:
            return None
        
        recent = self.history[-window:]
        return sum(m.total_duration for m in recent) / len(recent)
    
    def detect_regression(self, 
                         current_duration: float,
                         threshold_percent: float = 20.0,
                         window: int = 5) -> Tuple[bool, str]:
        """Detect performance regression.
        
        Args:
            current_duration: Duration of current test run
            threshold_percent: Percent increase to consider a regression
            window: Number of recent runs to use for baseline
            
        Returns:
            Tuple of (is_regression, message)
        """
        baseline = self.get_baseline_duration(window)
        
        if baseline is None:
            return False, "Insufficient history for regression detection"
        
        increase_percent = ((current_duration - baseline) / baseline) * 100
        
        if increase_percent > threshold_percent:
            return True, (
                f"Performance regression detected: "
                f"{current_duration:.2f}s vs baseline {baseline:.2f}s "
                f"(+{increase_percent:.1f}%)"
            )
        
        return False, f"Performance OK: {current_duration:.2f}s vs baseline {baseline:.2f}s ({increase_percent:+.1f}%)"
    
    def identify_slow_tests(self, 
                           threshold_seconds: float = 1.0) -> List[Tuple[str, float]]:
        """Identify slow tests from last run.
        
        Args:
            threshold_seconds: Duration threshold to consider a test slow
            
        Returns:
            List of (test_name, duration) tuples for slow tests
        """
        if not self.history or not self.history[-1].individual_tests:
            return []
        
        last_run = self.history[-1]
        slow_tests = [
            (name, duration) 
            for name, duration in last_run.individual_tests.items()
            if duration > threshold_seconds
        ]
        
        return sorted(slow_tests, key=lambda x: x[1], reverse=True)
    
    def get_trend(self, num_runs: int = 10) -> List[float]:
        """Get duration trend for recent runs.
        
        Args:
            num_runs: Number of recent runs to include
            
        Returns:
            List of durations from oldest to newest
        """
        recent = self.history[-num_runs:]
        return [m.total_duration for m in recent]
    
    def clear_history(self) -> None:
        """Clear all metrics history."""
        self.history = []
        if self.metrics_path.exists():
            self.metrics_path.unlink()


def parse_pytest_duration(output: str) -> Optional[float]:
    """Parse total duration from pytest output.
    
    Args:
        output: Pytest output string
        
    Returns:
        Duration in seconds, or None if not found
    """
    import re
    
    # Match patterns like "in 0.23s", "in 2.34s"
    match = re.search(r'in ([\d.]+)s', output)
    if match:
        return float(match.group(1))
    return None


def parse_pytest_results(output: str) -> Tuple[int, int]:
    """Parse test results from pytest output.
    
    Args:
        output: Pytest output string
        
    Returns:
        Tuple of (passed_count, failed_count)
    """
    import re
    
    # Match patterns like "5 passed", "2 failed"
    passed_match = re.search(r'(\d+) passed', output)
    failed_match = re.search(r'(\d+) failed', output)
    
    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    
    return passed, failed

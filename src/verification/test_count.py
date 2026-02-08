"""L3: Test count baseline validation.

Detect test deletion attacks by ensuring test count doesn't decrease.
Stores baseline on first run, compares on subsequent runs.
"""

import json
from pathlib import Path
from typing import Tuple
from datetime import datetime
from src.verification.layer import Layer, LayerResult


class CountBaselineLayer(Layer):
    """L3: Test count validation layer."""
    
    def __init__(self, baseline_path: str = '.test_baseline'):
        """Initialize test count layer.
        
        Args:
            baseline_path: Path to baseline file
        """
        super().__init__()
        self.baseline_path = baseline_path
    
    @property
    def name(self) -> str:
        """Layer name."""
        return "TestCount"
    
    @property
    def level(self) -> int:
        """Layer level (L3)."""
        return 3
    
    def run(self, test_count: int = None, **kwargs) -> LayerResult:
        """Check test count against baseline.
        
        Args:
            test_count: Number of tests collected
            **kwargs: Ignored (for compatibility)
            
        Returns:
            LayerResult with validation status
        """
        if test_count is None:
            return LayerResult(
                passed=True,
                message="No test count to validate"
            )
        
        baseline_file = Path(self.baseline_path)
        
        # Check if baseline exists (handle permission errors)
        try:
            baseline_exists = baseline_file.exists()
        except (OSError, PermissionError) as e:
            return LayerResult(
                passed=False,
                message=f"Cannot access baseline file: {str(e)}",
                error_details=[str(e)]
            )
        
        # First run: create baseline
        if not baseline_exists:
            result = _save_baseline(baseline_file, test_count)
            if not result[0]:
                return LayerResult(
                    passed=False,
                    message=result[1],
                    error_details=[result[1]]
                )
            return LayerResult(
                passed=True,
                message=f"Baseline created: {test_count} tests"
            )
        
        # Load baseline
        try:
            with baseline_file.open('r') as f:
                baseline_data = json.load(f)
            baseline_count = baseline_data.get('test_count', 0)
        except (json.JSONDecodeError, KeyError, IOError) as e:
            # Corrupted baseline, recreate
            result = _save_baseline(baseline_file, test_count)
            if not result[0]:
                return LayerResult(
                    passed=False,
                    message=result[1],
                    error_details=[result[1]]
                )
            return LayerResult(
                passed=True,
                message=f"Baseline recreated (was corrupted): {test_count} tests"
            )
        
        # Compare counts
        if test_count < baseline_count:
            error_msg = f"Test count decreased: {baseline_count} -> {test_count} (BLOCKED)"
            return LayerResult(
                passed=False,
                message=error_msg,
                error_details=[error_msg]
            )
        elif test_count > baseline_count:
            # Update baseline with new count
            result = _save_baseline(baseline_file, test_count)
            if not result[0]:
                # Baseline update failed but test count increased, still allow
                return LayerResult(
                    passed=True,
                    message=f"Test count increased: {baseline_count} -> {test_count} (baseline update failed: {result[1]})"
                )
            return LayerResult(
                passed=True,
                message=f"Test count increased: {baseline_count} -> {test_count} (baseline updated)"
            )
        else:
            return LayerResult(
                passed=True,
                message=f"Test count unchanged: {test_count} tests"
            )


def check_test_count(current_count: int, baseline_path: str = '.test_baseline') -> Tuple[bool, str]:
    """Check that test count hasn't decreased from baseline.

    Deprecated: Use CountBaselineLayer.run() instead.
    Kept for backwards compatibility.

    Args:
        current_count: Number of tests collected in current run
        baseline_path: Path to baseline file (default: .test_baseline)

    Returns:
        Tuple of (passed, message)
        - passed: True if count is >= baseline (or first run)
        - message: Human-readable status message
    """
    layer = CountBaselineLayer(baseline_path)
    result = layer.run(test_count=current_count)
    return result.passed, result.message


def _save_baseline(baseline_file: Path, test_count: int) -> Tuple[bool, str]:
    """Save baseline to file.
    
    Returns:
        Tuple of (success, error_message)
    """
    baseline_data = {
        'test_count': test_count,
        'updated_at': datetime.utcnow().isoformat()
    }
    try:
        with baseline_file.open('w') as f:
            json.dump(baseline_data, f, indent=2)
        return True, ""
    except (IOError, OSError, PermissionError) as e:
        return False, f"Failed to write baseline: {str(e)}"

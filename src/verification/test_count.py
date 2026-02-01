"""L3: Test count baseline validation.

Detect test deletion attacks by ensuring test count doesn't decrease.
Stores baseline on first run, compares on subsequent runs.
"""

import json
from pathlib import Path
from typing import Tuple
from datetime import datetime


def check_test_count(current_count: int, baseline_path: str = '.test_baseline') -> Tuple[bool, str]:
    """Check that test count hasn't decreased from baseline.
    
    Args:
        current_count: Number of tests collected in current run
        baseline_path: Path to baseline file (default: .test_baseline)
        
    Returns:
        Tuple of (passed, message)
        - passed: True if count is >= baseline (or first run)
        - message: Human-readable status message
    """
    baseline_file = Path(baseline_path)
    
    # Check if baseline exists (handle permission errors)
    try:
        baseline_exists = baseline_file.exists()
    except (OSError, PermissionError) as e:
        return False, f"Cannot access baseline file: {str(e)}"
    
    # First run: create baseline
    if not baseline_exists:
        result = _save_baseline(baseline_file, current_count)
        if not result[0]:
            return result  # Return error if save failed
        return True, f"Baseline created: {current_count} tests"
    
    # Load baseline
    try:
        with baseline_file.open('r') as f:
            baseline_data = json.load(f)
        baseline_count = baseline_data.get('test_count', 0)
    except (json.JSONDecodeError, KeyError, IOError) as e:
        # Corrupted baseline, recreate
        result = _save_baseline(baseline_file, current_count)
        if not result[0]:
            return result  # Return error if save failed
        return True, f"Baseline recreated (was corrupted): {current_count} tests"
    
    # Compare counts
    if current_count < baseline_count:
        return False, f"Test count decreased: {baseline_count} -> {current_count} (BLOCKED)"
    elif current_count > baseline_count:
        # Update baseline with new count
        result = _save_baseline(baseline_file, current_count)
        if not result[0]:
            # Baseline update failed but test count increased, still allow
            return True, f"Test count increased: {baseline_count} -> {current_count} (baseline update failed: {result[1]})"
        return True, f"Test count increased: {baseline_count} -> {current_count} (baseline updated)"
    else:
        return True, f"Test count unchanged: {current_count} tests"


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

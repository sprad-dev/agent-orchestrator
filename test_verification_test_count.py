"""Tests for L3 test count validation."""

import pytest
import tempfile
import json
from pathlib import Path
from src.verification.test_count import check_test_count


def test_baseline_creation():
    """First run should create baseline."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        baseline_path = f.name
        Path(baseline_path).unlink()  # Remove to test creation
        
        passed, message = check_test_count(10, baseline_path)
        
        assert passed is True
        assert 'Baseline created' in message
        assert '10 tests' in message
        
        # Verify baseline file exists
        assert Path(baseline_path).exists()
        
        with open(baseline_path) as bf:
            data = json.load(bf)
            assert data['test_count'] == 10
            assert 'updated_at' in data
        
        Path(baseline_path).unlink()


def test_count_increase_allowed():
    """Increasing test count should pass and update baseline."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        baseline_path = f.name
        
        # Create baseline with 10 tests
        check_test_count(10, baseline_path)
        
        # Increase to 15 tests
        passed, message = check_test_count(15, baseline_path)
        
        assert passed is True
        assert 'increased' in message.lower()
        assert '10 -> 15' in message
        
        # Verify baseline was updated
        with open(baseline_path) as bf:
            data = json.load(bf)
            assert data['test_count'] == 15
        
        Path(baseline_path).unlink()


def test_count_decrease_blocked():
    """Decreasing test count should fail."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        baseline_path = f.name
        
        # Create baseline with 10 tests
        check_test_count(10, baseline_path)
        
        # Decrease to 5 tests
        passed, message = check_test_count(5, baseline_path)
        
        assert passed is False
        assert 'decreased' in message.lower()
        assert '10 -> 5' in message
        assert 'BLOCKED' in message
        
        # Verify baseline was NOT updated
        with open(baseline_path) as bf:
            data = json.load(bf)
            assert data['test_count'] == 10
        
        Path(baseline_path).unlink()


def test_count_unchanged():
    """Same test count should pass."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        baseline_path = f.name
        
        # Create baseline with 10 tests
        check_test_count(10, baseline_path)
        
        # Run again with 10 tests
        passed, message = check_test_count(10, baseline_path)
        
        assert passed is True
        assert 'unchanged' in message.lower()
        assert '10 tests' in message
        
        Path(baseline_path).unlink()


def test_corrupted_baseline_recreated():
    """Corrupted baseline should be recreated."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        baseline_path = f.name
        f.write('not valid json')
        f.flush()
        
        passed, message = check_test_count(10, baseline_path)
        
        assert passed is True
        assert 'recreated' in message.lower()
        
        # Verify baseline is now valid
        with open(baseline_path) as bf:
            data = json.load(bf)
            assert data['test_count'] == 10
        
        Path(baseline_path).unlink()


def test_missing_baseline_creates_new():
    """Missing baseline file should create new one."""
    baseline_path = '/tmp/test_baseline_' + str(Path(tempfile.mktemp()).name)
    
    # Ensure file doesn't exist
    if Path(baseline_path).exists():
        Path(baseline_path).unlink()
    
    passed, message = check_test_count(20, baseline_path)
    
    assert passed is True
    assert 'created' in message.lower()
    
    Path(baseline_path).unlink()

"""Tests for L3 pytest output validation."""

import pytest
from src.verification.pytest_validator import validate_pytest_ran, parse_test_count


def test_zero_items_rejected():
    """Output with 0 items collected should be rejected."""
    output = """
============================= test session starts ==============================
collected 0 items

============================ no tests ran in 0.01s =============================
"""
    
    valid, message = validate_pytest_ran(output)
    
    assert valid is False
    assert 'collected 0 items' in message.lower()


def test_collection_error_rejected():
    """Collection errors should be rejected."""
    output = """
============================= test session starts ==============================
ERROR: file not found: tests/
"""
    
    valid, message = validate_pytest_ran(output)
    
    assert valid is False
    assert 'collection failed' in message.lower() or 'missing' in message.lower()


def test_valid_run_accepted():
    """Valid pytest run should be accepted."""
    output = """
============================= test session starts ==============================
collected 5 items

test_example.py .....                                                    [100%]

============================== 5 passed in 0.23s ===============================
"""
    
    valid, message = validate_pytest_ran(output)
    
    assert valid is True
    assert '5 test' in message.lower()


def test_parse_collection_count():
    """Should correctly parse test count."""
    output = "collected 42 items"
    assert parse_test_count(output) == 42
    
    output = "collected 1 item"
    assert parse_test_count(output) == 1
    
    output = "no collection here"
    assert parse_test_count(output) == 0


def test_missing_collection_phase():
    """Output without collection phase should be rejected."""
    output = """
============================= test session starts ==============================
Some other output without collection
"""
    
    valid, message = validate_pytest_ran(output)
    
    assert valid is False
    assert 'missing collection' in message.lower()


def test_multiple_items_accepted():
    """Multiple test items should be accepted."""
    output = """
============================= test session starts ==============================
collected 123 items

test_file1.py ......                                                      [ 15%]
test_file2.py .......                                                     [100%]

============================ 123 passed in 2.34s ===============================
"""
    
    valid, message = validate_pytest_ran(output)
    
    assert valid is True
    assert '123 test' in message.lower()


def test_collection_with_failures():
    """Collections with test failures should still be valid (tests ran)."""
    output = """
============================= test session starts ==============================
collected 10 items

test_example.py ..F.F.....                                               [100%]

============================== 8 passed, 2 failed in 0.45s ====================
"""
    
    valid, message = validate_pytest_ran(output)
    
    assert valid is True
    assert '10 test' in message.lower()


def test_test_count_check_runs_on_failed_tests():
    """Critical: Test count check must run even when tests fail to detect test deletion."""
    import tempfile
    from pathlib import Path
    from src.verification.runner import VerificationRunner
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.baseline') as f:
        baseline_path = f.name
        Path(baseline_path).unlink()
        
        # Create a runner that will "run" pytest with simulated failing tests
        runner = VerificationRunner(verify_cmd="echo 'mock pytest'", baseline_path=baseline_path)
        
        # Simulate pytest output with 10 tests but some failures
        pytest_output_10_tests = """
============================= test session starts ==============================
collected 10 items

test_example.py ..F.F.....                                               [100%]

============================ 8 passed, 2 failed in 0.45s ====================
"""
        
        # First, manually set up baseline with 10 tests
        from src.verification.test_count import check_test_count
        check_test_count(10, baseline_path)
        
        # Now simulate a run where tests were deleted (5 tests) and tests fail
        pytest_output_5_tests = """
============================= test session starts ==============================
collected 5 items

test_example.py F....                                                    [100%]

============================ 4 passed, 1 failed in 0.23s ===================
"""
        
        # Manually test the logic by checking if test count validation would catch this
        from src.verification.pytest_validator import parse_test_count, validate_pytest_ran
        
        # First verify pytest_valid would be True (tests were collected)
        pytest_valid, _ = validate_pytest_ran(pytest_output_5_tests)
        assert pytest_valid is True, "Pytest validation should pass - tests were collected"
        
        # Then verify test count check would catch the deletion
        test_count = parse_test_count(pytest_output_5_tests)
        assert test_count == 5
        
        count_passed, count_msg = check_test_count(test_count, baseline_path)
        assert count_passed is False, "Test count check should FAIL - tests were deleted (10 -> 5)"
        assert 'decreased' in count_msg.lower()
        assert '10 -> 5' in count_msg
        
        Path(baseline_path).unlink()

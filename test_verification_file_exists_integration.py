"""Integration tests for L1 file existence check with VerificationRunner."""

import pytest
import tempfile
from pathlib import Path
from src.verification.runner import VerificationRunner


def test_runner_with_existing_files(monkeypatch):
    """VerificationRunner should pass L1 check for existing files."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.baseline', delete=False) as baseline:
        f.write('def test_example():\n    assert True\n')
        f.flush()
        
        runner = VerificationRunner(baseline_path=baseline.name)
        
        # Mock pytest to avoid actually running tests
        def mock_run_shell(cmd, ignore_error=False):
            return True, "collected 1 item\n\n1 passed in 0.01s", ""
        
        monkeypatch.setattr('src.verification.runner.run_shell', mock_run_shell)
        
        passed, output = runner.run(modified_files=[f.name])
        
        assert passed is True
        assert '✓ L1 File existence check passed' in output
        
        Path(f.name).unlink()
        Path(baseline.name).unlink()


def test_runner_with_missing_files():
    """VerificationRunner should fail L1 check for missing files."""
    runner = VerificationRunner()
    
    passed, output = runner.run(modified_files=['/nonexistent/file.py'])
    
    assert passed is False
    assert 'FILE EXISTENCE CHECK FAILED' in output
    assert 'File not found' in output
    assert '/nonexistent/file.py' in output


def test_runner_skips_l1_when_no_files(monkeypatch):
    """VerificationRunner should skip L1 check when no files provided."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.baseline', delete=False) as baseline:
        runner = VerificationRunner(baseline_path=baseline.name)
        
        # Mock pytest to avoid actually running tests
        def mock_run_shell(cmd, ignore_error=False):
            return True, "collected 1 item\n\n1 passed in 0.01s", ""
        
        monkeypatch.setattr('src.verification.runner.run_shell', mock_run_shell)
        
        passed, output = runner.run(modified_files=None)
        
        assert passed is True
        assert 'L1 File existence check' not in output
        
        Path(baseline.name).unlink()


def test_runner_skips_l1_when_disabled(monkeypatch):
    """VerificationRunner should skip L1 check when disabled."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.baseline', delete=False) as baseline:
        f.write('def test_example():\n    assert True\n')
        f.flush()
        
        runner = VerificationRunner(baseline_path=baseline.name)
        runner.enable_file_exists_check = False
        
        # Mock pytest to avoid actually running tests
        def mock_run_shell(cmd, ignore_error=False):
            return True, "collected 1 item\n\n1 passed in 0.01s", ""
        
        monkeypatch.setattr('src.verification.runner.run_shell', mock_run_shell)
        
        passed, output = runner.run(modified_files=[f.name])
        
        assert passed is True
        assert 'L1 File existence check' not in output
        
        Path(f.name).unlink()
        Path(baseline.name).unlink()


def test_l1_runs_before_syntax_check(monkeypatch):
    """L1 should run before L2 syntax check and fail fast."""
    runner = VerificationRunner()
    
    # If L1 fails, L2 should not run (and thus shouldn't call py_compile)
    passed, output = runner.run(modified_files=['/nonexistent/file.py'])
    
    assert passed is False
    assert 'FILE EXISTENCE CHECK FAILED' in output
    assert 'SYNTAX CHECK' not in output


def test_l1_checks_multiple_files_mixed(monkeypatch):
    """L1 should detect missing files in a mix of existing and missing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def test_example():\n    assert True\n')
        f.flush()
        
        runner = VerificationRunner()
        
        passed, output = runner.run(modified_files=[f.name, '/missing/file.py'])
        
        assert passed is False
        assert 'FILE EXISTENCE CHECK FAILED' in output
        assert '/missing/file.py' in output
        
        Path(f.name).unlink()


def test_l1_allows_empty_file_list():
    """L1 should handle empty file list gracefully."""
    runner = VerificationRunner()
    
    # Empty list should be treated as no files to check
    # This is implicitly tested by passing modified_files=[] which should skip L1
    # But let's be explicit
    files_exist, errors = runner.run_file_exists_check([])
    
    assert files_exist is True
    assert len(errors) == 0


def test_l1_integration_with_all_layers(monkeypatch):
    """L1 should integrate smoothly with other verification layers."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def test_example():\n    assert True\n')
        f.flush()
        
        runner = VerificationRunner()
        
        # Mock pytest to return successful test run
        def mock_run_shell(cmd, ignore_error=False):
            return True, "collected 10 items\n\n10 passed in 0.5s", ""
        
        monkeypatch.setattr('src.verification.runner.run_shell', mock_run_shell)
        
        passed, output = runner.run(modified_files=[f.name])
        
        assert passed is True
        # Should see all layers execute
        assert '✓ L1 File existence check passed' in output
        assert '✓ L2 Syntax check passed' in output
        assert '✓ L3 Pytest validation' in output
        
        Path(f.name).unlink()


def test_l1_error_messages_clear():
    """L1 errors should be clear and actionable."""
    runner = VerificationRunner()
    
    passed, output = runner.run(modified_files=[
        '/path/to/missing1.py',
        '/path/to/missing2.py'
    ])
    
    assert passed is False
    assert 'FILE EXISTENCE CHECK FAILED' in output
    assert 'File not found' in output
    # Both missing files should be reported
    assert 'missing1.py' in output
    assert 'missing2.py' in output

"""Tests for L3 coverage analysis for changed files."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.verification.coverage_check import (
    get_changed_files,
    run_coverage_analysis,
    check_coverage,
    get_coverage_report
)


def test_get_changed_files_empty():
    """Should return empty list when no changes."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            stdout='',
            returncode=0
        )
        
        files = get_changed_files()
        
        assert files == []


def test_get_changed_files_filters_python():
    """Should only return Python files."""
    with patch('subprocess.run') as mock_run:
        with patch('pathlib.Path.exists') as mock_exists:
            mock_run.return_value = MagicMock(
                stdout='file1.py\nfile2.txt\nfile3.py\nREADME.md',
                returncode=0
            )
            mock_exists.return_value = True
            
            files = get_changed_files()
            
            assert files == ['file1.py', 'file3.py']


def test_get_changed_files_error():
    """Should return empty list on git error."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = Exception("git error")
        
        files = get_changed_files()
        
        assert files == []


def test_run_coverage_analysis_no_files():
    """Should skip when no changed files."""
    passed, message, coverage_data = run_coverage_analysis(changed_files=[])
    
    assert passed is True
    assert "No changed Python files" in message
    assert coverage_data == {}


def test_run_coverage_analysis_nonexistent_files():
    """Should skip nonexistent files."""
    passed, message, coverage_data = run_coverage_analysis(
        changed_files=['nonexistent.py']
    )
    
    assert passed is True
    assert "No existing Python files" in message
    assert coverage_data == {}


def test_run_coverage_analysis_with_mock_coverage():
    """Test coverage analysis with mocked coverage data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = Path(tmpdir) / 'test_module.py'
        test_file.write_text('def test_func():\n    return True\n')
        
        # Mock coverage data
        mock_coverage_data = {
            'files': {
                str(test_file.resolve()): {
                    'summary': {
                        'percent_covered': 85.5,
                        'covered_lines': 17,
                        'num_statements': 20
                    },
                    'missing_lines': [3, 5, 8]
                }
            }
        }
        
        with patch('subprocess.run') as mock_run:
            # Mock coverage run success
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            # Mock coverage json generation
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_coverage_data)
                
                with patch('json.load', return_value=mock_coverage_data):
                    passed, message, coverage_data = run_coverage_analysis(
                        changed_files=[str(test_file)]
                    )
                    
                    assert str(test_file) in message
                    assert '85.5%' in message


def test_run_coverage_analysis_enforces_minimum():
    """Test that minimum coverage threshold is enforced."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / 'low_coverage.py'
        test_file.write_text('def func():\n    pass\n')
        
        mock_coverage_data = {
            'files': {
                str(test_file.resolve()): {
                    'summary': {
                        'percent_covered': 60.0,
                        'covered_lines': 6,
                        'num_statements': 10
                    },
                    'missing_lines': [2, 3, 4, 5]
                }
            }
        }
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__.return_value = mock_file
                mock_open.return_value = mock_file
                
                with patch('json.load', return_value=mock_coverage_data):
                    passed, message, coverage_data = run_coverage_analysis(
                        changed_files=[str(test_file)],
                        min_coverage=80.0
                    )
                    
                    assert passed is False
                    assert 'FAILED' in message
                    assert 'below minimum' in message
                    assert '80' in message


def test_run_coverage_analysis_meets_minimum():
    """Test that passing coverage threshold succeeds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / 'good_coverage.py'
        test_file.write_text('def func():\n    pass\n')
        
        mock_coverage_data = {
            'files': {
                str(test_file.resolve()): {
                    'summary': {
                        'percent_covered': 95.0,
                        'covered_lines': 19,
                        'num_statements': 20
                    },
                    'missing_lines': [10]
                }
            }
        }
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__.return_value = mock_file
                mock_open.return_value = mock_file
                
                with patch('json.load', return_value=mock_coverage_data):
                    passed, message, coverage_data = run_coverage_analysis(
                        changed_files=[str(test_file)],
                        min_coverage=80.0
                    )
                    
                    assert passed is True
                    assert '95.0%' in message


def test_run_coverage_analysis_multiple_files():
    """Test coverage analysis with multiple files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / 'module1.py'
        file2 = Path(tmpdir) / 'module2.py'
        file1.write_text('def func1():\n    pass\n')
        file2.write_text('def func2():\n    pass\n')
        
        mock_coverage_data = {
            'files': {
                str(file1.resolve()): {
                    'summary': {
                        'percent_covered': 90.0,
                        'covered_lines': 9,
                        'num_statements': 10
                    },
                    'missing_lines': [5]
                },
                str(file2.resolve()): {
                    'summary': {
                        'percent_covered': 80.0,
                        'covered_lines': 8,
                        'num_statements': 10
                    },
                    'missing_lines': [3, 7]
                }
            }
        }
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__.return_value = mock_file
                mock_open.return_value = mock_file
                
                with patch('json.load', return_value=mock_coverage_data):
                    passed, message, coverage_data = run_coverage_analysis(
                        changed_files=[str(file1), str(file2)]
                    )
                    
                    assert '2 file(s) analyzed' in message
                    assert '85.0%' in message  # Average of 90% and 80%
                    assert str(file1) in message
                    assert str(file2) in message


def test_run_coverage_analysis_timeout():
    """Test that coverage analysis handles timeout."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / 'test.py'
        test_file.write_text('pass')
        
        with patch('subprocess.run') as mock_run:
            from subprocess import TimeoutExpired
            mock_run.side_effect = TimeoutExpired('coverage', 60)
            
            passed, message, coverage_data = run_coverage_analysis(
                changed_files=[str(test_file)]
            )
            
            assert passed is False
            assert 'timed out' in message.lower()
            assert coverage_data == {}


def test_run_coverage_analysis_error():
    """Test that coverage analysis handles general errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / 'test.py'
        test_file.write_text('pass')
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Coverage error")
            
            passed, message, coverage_data = run_coverage_analysis(
                changed_files=[str(test_file)]
            )
            
            assert passed is False
            assert 'error' in message.lower()
            assert coverage_data == {}


def test_check_coverage_wrapper():
    """Test check_coverage convenience function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / 'test.py'
        test_file.write_text('pass')
        
        mock_coverage_data = {
            'files': {
                str(test_file.resolve()): {
                    'summary': {
                        'percent_covered': 85.0,
                        'covered_lines': 17,
                        'num_statements': 20
                    },
                    'missing_lines': [3, 5, 8]
                }
            }
        }
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__.return_value = mock_file
                mock_open.return_value = mock_file
                
                with patch('json.load', return_value=mock_coverage_data):
                    passed, message = check_coverage(
                        changed_files=[str(test_file)],
                        min_coverage=80.0
                    )
                    
                    assert passed is True
                    assert isinstance(message, str)


def test_get_coverage_report():
    """Test get_coverage_report returns coverage data without threshold check."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / 'test.py'
        test_file.write_text('pass')
        
        mock_coverage_data = {
            'files': {
                str(test_file.resolve()): {
                    'summary': {
                        'percent_covered': 50.0,
                        'covered_lines': 5,
                        'num_statements': 10
                    },
                    'missing_lines': [1, 2, 3, 4, 5]
                }
            }
        }
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__.return_value = mock_file
                mock_open.return_value = mock_file
                
                with patch('json.load', return_value=mock_coverage_data):
                    coverage_data = get_coverage_report(changed_files=[str(test_file)])
                    
                    # Should return data even with low coverage (no threshold enforcement)
                    assert str(test_file) in coverage_data
                    assert coverage_data[str(test_file)]['percent_covered'] == 50.0


def test_coverage_with_file_not_in_report():
    """Test handling of files that exist but aren't in coverage report."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / 'uncovered.py'
        test_file.write_text('# Empty file')
        
        mock_coverage_data = {
            'files': {}  # File not in coverage report
        }
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__.return_value = mock_file
                mock_open.return_value = mock_file
                
                with patch('json.load', return_value=mock_coverage_data):
                    passed, message, coverage_data = run_coverage_analysis(
                        changed_files=[str(test_file)]
                    )
                    
                    # Should handle missing files gracefully
                    assert str(test_file) in coverage_data
                    assert coverage_data[str(test_file)]['percent_covered'] == 0.0


def test_integration_with_runner():
    """Test coverage integration with VerificationRunner."""
    from src.verification.runner import VerificationRunner
    from src.verification.config import VerificationConfig
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / 'test_module.py'
        test_file.write_text('def test():\n    pass\n')
        
        # Create config with coverage enabled
        config = VerificationConfig(
            enable_coverage_check=True,
            coverage_minimum_percent=70.0,
            enable_syntax_check=False,
            enable_test_count_check=False,
            enable_pytest_validation=False
        )
        
        runner = VerificationRunner(config=config)
        
        # Verify coverage settings are loaded
        assert runner.enable_coverage_check is True
        assert runner.min_coverage == 70.0

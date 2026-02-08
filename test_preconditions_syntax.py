"""Tests for precondition syntax check."""

import pytest
import tempfile
from pathlib import Path
from src.preconditions import check_syntax


def test_valid_syntax_passes():
    """Valid Python syntax should pass."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def hello():\n    return "world"\n')
        f.flush()

        passed, message = check_syntax([f.name])

        assert passed is True
        assert '1 file(s) checked' in message

        Path(f.name).unlink()


def test_invalid_syntax_fails():
    """Invalid Python syntax should fail."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def broken(\n    return "missing colon"\n')
        f.flush()

        passed, message = check_syntax([f.name])

        assert passed is False
        assert 'Syntax errors found' in message

        Path(f.name).unlink()


def test_multiple_files_all_valid():
    """Multiple valid files should pass."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f1, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f2:
        f1.write('x = 1\n')
        f1.flush()
        f2.write('y = 2\n')
        f2.flush()

        passed, message = check_syntax([f1.name, f2.name])

        assert passed is True
        assert '2 file(s) checked' in message

        Path(f1.name).unlink()
        Path(f2.name).unlink()


def test_multiple_files_one_invalid():
    """One invalid file should fail entire check."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f1, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f2:
        f1.write('x = 1\n')
        f1.flush()
        f2.write('def bad(\n')  # Syntax error
        f2.flush()

        passed, message = check_syntax([f1.name, f2.name])

        assert passed is False
        assert 'Syntax errors found' in message
        assert f2.name in message

        Path(f1.name).unlink()
        Path(f2.name).unlink()


def test_non_python_files_skipped():
    """Non-Python files should be skipped."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write('not python code')
        f.flush()

        passed, message = check_syntax([f.name])

        assert passed is True
        assert 'No Python files' in message or '0 file(s) checked' in message

        Path(f.name).unlink()


def test_missing_files_skipped():
    """Missing files should be skipped."""
    passed, message = check_syntax(['/nonexistent/file.py'])

    assert passed is True
    assert 'No Python files' in message or '0 file(s) checked' in message


def test_empty_file_list():
    """Empty file list should pass."""
    passed, message = check_syntax([])

    assert passed is True
    assert 'No Python files' in message

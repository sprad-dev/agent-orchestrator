"""Tests for L2 syntax validation."""

import pytest
import tempfile
from pathlib import Path
from src.verification.syntax_check import validate_python_syntax


def test_valid_syntax_passes():
    """Valid Python files should pass syntax check."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def hello():\n    return "world"\n')
        f.flush()
        
        passed, errors = validate_python_syntax([f.name])
        
        assert passed is True
        assert len(errors) == 0
        
        Path(f.name).unlink()


def test_invalid_syntax_fails():
    """Invalid Python files should fail syntax check."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def broken(\n    return "oops"\n')  # Missing closing paren
        f.flush()
        
        passed, errors = validate_python_syntax([f.name])
        
        assert passed is False
        assert len(errors) == 1
        assert f.name in errors[0]
        
        Path(f.name).unlink()


def test_non_python_files_skipped():
    """Non-Python files should be skipped."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write('not python code')
        f.flush()
        
        passed, errors = validate_python_syntax([f.name])
        
        assert passed is True
        assert len(errors) == 0
        
        Path(f.name).unlink()


def test_syntax_error_messages():
    """Syntax errors should include helpful messages."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('if True\n    pass')  # Missing colon
        f.flush()
        
        passed, errors = validate_python_syntax([f.name])
        
        assert passed is False
        assert len(errors) == 1
        assert 'invalid syntax' in errors[0].lower() or 'error' in errors[0].lower()
        
        Path(f.name).unlink()


def test_missing_file_handled():
    """Missing files should be handled gracefully."""
    passed, errors = validate_python_syntax(['/nonexistent/file.py'])
    
    assert passed is True
    assert len(errors) == 0


def test_multiple_files():
    """Should validate multiple files."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f1, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f2:
        
        f1.write('x = 1\n')
        f1.flush()
        
        f2.write('def bad(\n')  # Syntax error
        f2.flush()
        
        passed, errors = validate_python_syntax([f1.name, f2.name])
        
        assert passed is False
        assert len(errors) == 1
        assert f2.name in errors[0]
        
        Path(f1.name).unlink()
        Path(f2.name).unlink()

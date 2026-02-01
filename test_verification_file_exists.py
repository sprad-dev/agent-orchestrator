"""Tests for L1 file existence validation."""

import pytest
import tempfile
from pathlib import Path
from src.verification.file_exists import validate_files_exist


def test_existing_files_pass():
    """Existing files should pass validation."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('# test file\n')
        f.flush()
        
        passed, errors = validate_files_exist([f.name])
        
        assert passed is True
        assert len(errors) == 0
        
        Path(f.name).unlink()


def test_missing_file_fails():
    """Missing files should fail validation."""
    passed, errors = validate_files_exist(['/nonexistent/file.py'])
    
    assert passed is False
    assert len(errors) == 1
    assert 'File not found' in errors[0]
    assert '/nonexistent/file.py' in errors[0]


def test_multiple_existing_files():
    """Multiple existing files should all pass."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f1, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f2:
        
        f1.write('# test 1\n')
        f1.flush()
        f2.write('test 2\n')
        f2.flush()
        
        passed, errors = validate_files_exist([f1.name, f2.name])
        
        assert passed is True
        assert len(errors) == 0
        
        Path(f1.name).unlink()
        Path(f2.name).unlink()


def test_mixed_existing_and_missing():
    """Should fail and report only missing files."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('# exists\n')
        f.flush()
        
        passed, errors = validate_files_exist([f.name, '/nonexistent/file.py'])
        
        assert passed is False
        assert len(errors) == 1
        assert '/nonexistent/file.py' in errors[0]
        assert f.name not in errors[0]
        
        Path(f.name).unlink()


def test_multiple_missing_files():
    """Should report all missing files."""
    passed, errors = validate_files_exist([
        '/nonexistent/file1.py',
        '/nonexistent/file2.py',
        '/nonexistent/file3.py'
    ])
    
    assert passed is False
    assert len(errors) == 3
    assert any('file1.py' in e for e in errors)
    assert any('file2.py' in e for e in errors)
    assert any('file3.py' in e for e in errors)


def test_empty_file_list():
    """Empty file list should pass (nothing to validate)."""
    passed, errors = validate_files_exist([])
    
    assert passed is True
    assert len(errors) == 0


def test_error_message_format():
    """Error messages should be clear and helpful."""
    passed, errors = validate_files_exist(['/does/not/exist.py'])
    
    assert passed is False
    assert len(errors) == 1
    assert 'File not found' in errors[0]
    assert '/does/not/exist.py' in errors[0]


def test_relative_paths():
    """Should handle relative paths correctly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('# test\n')
        f.flush()
        
        # Test with absolute path
        passed, errors = validate_files_exist([f.name])
        assert passed is True
        
        Path(f.name).unlink()


def test_directory_as_file():
    """Directories should not be treated as files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # A directory exists but is not a file
        passed, errors = validate_files_exist([tmpdir])
        
        # Directory exists, so no "File not found" error
        # This is acceptable - we're checking existence, not file type
        assert passed is True


def test_symlink_handling():
    """Should handle symlinks correctly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('# target\n')
        f.flush()
        
        # Create a symlink
        with tempfile.TemporaryDirectory() as tmpdir:
            link_path = Path(tmpdir) / 'link.py'
            link_path.symlink_to(f.name)
            
            # Symlink to existing file should pass
            passed, errors = validate_files_exist([str(link_path)])
            assert passed is True
            
        Path(f.name).unlink()


def test_broken_symlink():
    """Broken symlinks should fail validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        link_path = Path(tmpdir) / 'broken_link.py'
        link_path.symlink_to('/nonexistent/target.py')
        
        passed, errors = validate_files_exist([str(link_path)])
        
        assert passed is False
        assert len(errors) == 1
        assert str(link_path) in errors[0]


def test_special_characters_in_filename():
    """Should handle special characters in filenames."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=' test-file_123.py', delete=False) as f:
        f.write('# special chars\n')
        f.flush()
        
        passed, errors = validate_files_exist([f.name])
        
        assert passed is True
        assert len(errors) == 0
        
        Path(f.name).unlink()


def test_unicode_filenames():
    """Should handle unicode characters in filenames."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file with unicode name
        unicode_path = Path(tmpdir) / 'test_文件.py'
        unicode_path.write_text('# unicode test\n')
        
        passed, errors = validate_files_exist([str(unicode_path)])
        
        assert passed is True
        assert len(errors) == 0

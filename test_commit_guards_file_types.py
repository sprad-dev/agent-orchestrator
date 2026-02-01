"""Tests for commit guards file type validation."""

import pytest
from unittest.mock import patch
from src.guards.commit import CommitGuard


class TestFileTypeValidation:
    """Test file type validation in commit guards."""
    
    @pytest.fixture
    def guard(self):
        """Create a CommitGuard instance."""
        return CommitGuard()
    
    def test_get_extension_simple(self, guard):
        """Test extracting simple file extensions."""
        assert guard._get_extension('test.py') == '.py'
        assert guard._get_extension('file.txt') == '.txt'
        assert guard._get_extension('script.sh') == '.sh'
    
    def test_get_extension_no_extension(self, guard):
        """Test files without extensions."""
        assert guard._get_extension('README') == ''
        assert guard._get_extension('Makefile') == ''
    
    def test_get_extension_multiple_dots(self, guard):
        """Test files with multiple dots."""
        assert guard._get_extension('file.tar.gz') == '.gz'
        assert guard._get_extension('test.backup.py') == '.py'
    
    def test_get_extension_path(self, guard):
        """Test extracting extensions from paths."""
        assert guard._get_extension('src/module/test.py') == '.py'
        assert guard._get_extension('/absolute/path/file.md') == '.md'
    
    @patch('src.guards.commit.run_shell')
    def test_check_file_types_allowed_python(self, mock_run_shell, guard):
        """Test that Python files pass validation."""
        mock_run_shell.return_value = (True, 'test.py\nmodule.py\n', 0)
        passed, issues = guard.check_file_types()
        assert passed is True
        assert len(issues) == 0
    
    @patch('src.guards.commit.run_shell')
    def test_check_file_types_blocked_binary_exe(self, mock_run_shell, guard):
        """Test that executable files are blocked."""
        mock_run_shell.return_value = (True, 'program.exe\n', 0)
        passed, issues = guard.check_file_types()
        assert passed is False
        assert 'program.exe' in issues[0]
        assert '.exe' in issues[0]
    
    @patch('src.guards.commit.run_shell')
    def test_check_file_types_custom_allowed(self, mock_run_shell):
        """Test custom allowed extensions."""
        guard = CommitGuard(allowed_extensions={'.py', '.js', '.ts'})
        mock_run_shell.return_value = (True, 'script.js\n', 0)
        passed, issues = guard.check_file_types()
        assert passed is True
        assert len(issues) == 0


class TestBinaryContentDetection:
    """Test binary content detection."""
    
    @pytest.fixture
    def guard(self):
        """Create a CommitGuard instance."""
        return CommitGuard()
    
    @patch('src.guards.commit.run_shell')
    def test_is_binary_content_text_file(self, mock_run_shell, guard):
        """Test that text files are not detected as binary."""
        mock_run_shell.side_effect = [(True, '', 0), (True, 'text\n', 0)]
        result = guard._is_binary_content('test.txt')
        assert result is False
    
    @patch('src.guards.commit.run_shell')
    def test_is_binary_content_binary_file(self, mock_run_shell, guard):
        """Test that binary files are detected."""
        mock_run_shell.side_effect = [(True, '', 0), (True, 'binary\n', 0)]
        result = guard._is_binary_content('app.exe')
        assert result is True


class TestGuardConfiguration:
    """Test guard configuration options."""
    
    def test_default_allowed_extensions(self):
        """Test default allowed extensions are set correctly."""
        guard = CommitGuard()
        assert '.py' in guard.allowed_extensions
        assert '.md' in guard.allowed_extensions
        assert '.json' in guard.allowed_extensions
        assert '.yaml' in guard.allowed_extensions
        assert '.sh' in guard.allowed_extensions
    
    def test_default_blocked_extensions(self):
        """Test default blocked extensions are set correctly."""
        guard = CommitGuard()
        assert '.exe' in guard.blocked_extensions
        assert '.dll' in guard.blocked_extensions
        assert '.so' in guard.blocked_extensions
        assert '.png' in guard.blocked_extensions
        assert '.zip' in guard.blocked_extensions

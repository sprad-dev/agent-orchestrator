"""Tests for L6 static test quality analysis layer."""

import tempfile
import os
import pytest
from pathlib import Path

from src.verification.test_quality import (
    TestQualityLayer,
    analyze_test_file,
    analyze_test_quality,
    find_test_files,
)


class TestAnalyzeTestFile:
    """Test the AST-based test file analyzer."""

    def _write_test_file(self, tmpdir, filename, content):
        """Write a test file and return its path."""
        path = os.path.join(tmpdir, filename)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_no_assertion_detected(self):
        """Test that functions with zero assertions are flagged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_test_file(tmpdir, "test_example.py", '''
def test_does_nothing():
    x = 1 + 1
    y = x * 2
''')
            issues = analyze_test_file(path)
            assert len(issues) == 1
            assert issues[0].issue_type == "no_assertion"
            assert issues[0].function == "test_does_nothing"

    def test_mock_only_detected(self):
        """Test that mock-only tests are flagged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_test_file(tmpdir, "test_mocks.py", '''
def test_calls_service(self):
    mock_svc = MagicMock()
    mock_svc.process("data")
    mock_svc.process.assert_called_once_with("data")
''')
            issues = analyze_test_file(path)
            assert len(issues) == 1
            assert issues[0].issue_type == "mock_only"

    def test_trivial_assert_true(self):
        """Test that assertTrue(True) is flagged as trivial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_test_file(tmpdir, "test_trivial.py", '''
def test_trivial(self):
    self.assertTrue(True)
''')
            issues = analyze_test_file(path)
            assert len(issues) == 1
            assert issues[0].issue_type == "trivial_assertion"

    def test_trivial_assert_is_not_none(self):
        """Test that assertIsNotNone(result) alone is trivial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_test_file(tmpdir, "test_trivial2.py", '''
def test_not_none(self):
    result = some_func()
    self.assertIsNotNone(result)
''')
            issues = analyze_test_file(path)
            assert len(issues) == 1
            assert issues[0].issue_type == "trivial_assertion"

    def test_real_assertions_pass(self):
        """Test that meaningful assertions produce no issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_test_file(tmpdir, "test_good.py", '''
def test_addition():
    assert 1 + 1 == 2

def test_string():
    result = "hello"
    assert result == "hello"
''')
            issues = analyze_test_file(path)
            assert len(issues) == 0

    def test_mixed_mock_and_value_assertions(self):
        """Test that mock + value assertions are not flagged as mock-only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_test_file(tmpdir, "test_mixed.py", '''
def test_calls_and_checks(self):
    mock_svc = MagicMock()
    result = mock_svc.process("data")
    mock_svc.process.assert_called_once_with("data")
    assert result is not None
''')
            issues = analyze_test_file(path)
            assert len(issues) == 0

    def test_non_test_functions_ignored(self):
        """Test that helper functions are not analyzed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_test_file(tmpdir, "test_helpers.py", '''
def helper():
    x = 1

def test_real():
    assert 1 == 1
''')
            issues = analyze_test_file(path)
            assert len(issues) == 0

    def test_syntax_error_file_skipped(self):
        """Test that files with syntax errors don't crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_test_file(tmpdir, "test_broken.py", '''
def test_broken(
    # missing closing paren
''')
            issues = analyze_test_file(path)
            assert len(issues) == 0

    def test_plain_assert_true_literal(self):
        """Test that bare 'assert True' is flagged as trivial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_test_file(tmpdir, "test_bare.py", '''
def test_bare_assert():
    assert True
''')
            issues = analyze_test_file(path)
            assert len(issues) == 1
            assert issues[0].issue_type == "trivial_assertion"


class TestFindTestFiles:
    """Test the test file discovery."""

    def test_finds_test_files(self):
        """Test that test_*.py files are found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            open(os.path.join(tmpdir, "test_one.py"), "w").close()
            open(os.path.join(tmpdir, "test_two.py"), "w").close()
            open(os.path.join(tmpdir, "helper.py"), "w").close()

            files = find_test_files(tmpdir)
            basenames = [os.path.basename(f) for f in files]
            assert "test_one.py" in basenames
            assert "test_two.py" in basenames
            assert "helper.py" not in basenames

    def test_finds_suffix_test_files(self):
        """Test that *_test.py files are found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "module_test.py"), "w").close()
            files = find_test_files(tmpdir)
            assert len(files) == 1

    def test_skips_pycache(self):
        """Test that __pycache__ dirs are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, "__pycache__")
            os.makedirs(cache_dir)
            open(os.path.join(cache_dir, "test_cached.py"), "w").close()
            files = find_test_files(tmpdir)
            assert len(files) == 0


class TestTestQualityLayer:
    """Test the L6 TestQualityLayer."""

    def test_layer_properties(self):
        """Test layer name and level."""
        layer = TestQualityLayer()
        assert layer.name == "TestQuality"
        assert layer.level == 60

    def test_no_issues_message(self):
        """Test output when all tests are clean."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_clean.py")
            with open(path, "w") as f:
                f.write("def test_good():\n    assert 1 == 1\n")

            layer = TestQualityLayer(project_path=tmpdir)
            result = layer.run(test_files=[path])
            assert result.passed is True
            assert "all tests" in result.message.lower()

    def test_issues_found_advisory(self):
        """Test that issues are reported but layer still passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_bad.py")
            with open(path, "w") as f:
                f.write("def test_nothing():\n    x = 1\n")

            layer = TestQualityLayer(project_path=tmpdir)
            result = layer.run(test_files=[path])
            assert result.passed is True  # Advisory — always passes
            assert "1 issue" in result.message
            assert len(result.error_details) > 0

    def test_discovers_files_when_none_passed(self):
        """Test that layer discovers test files from project_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_auto.py")
            with open(path, "w") as f:
                f.write("def test_auto():\n    assert 2 == 2\n")

            layer = TestQualityLayer(project_path=tmpdir)
            result = layer.run()  # No test_files arg
            assert result.passed is True

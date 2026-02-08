"""Tests for L7 LLM adversarial review layer."""

import tempfile
import os
from unittest.mock import patch, MagicMock
import pytest

from src.verification.adversarial_review import (
    AdversarialReviewLayer,
    run_adversarial_review,
    _read_test_files,
    _parse_issues,
)


class TestParseIssues:
    """Test LLM output parsing."""

    def test_parses_issue_lines(self):
        """Test that ISSUE: lines are extracted."""
        output = """Looking at the tests...

ISSUE: test_foo.py::test_add — hardcoded return value
ISSUE: test_bar.py::test_calc — no edge case testing

Overall the tests could use improvement.
"""
        issues = _parse_issues(output)
        assert len(issues) == 2
        assert "test_foo.py::test_add" in issues[0]
        assert "test_bar.py::test_calc" in issues[1]

    def test_no_issues_found(self):
        """Test output with no ISSUE: lines."""
        output = "All tests look good. NO_ISSUES_FOUND"
        issues = _parse_issues(output)
        assert len(issues) == 0

    def test_empty_output(self):
        """Test empty string input."""
        assert _parse_issues("") == []


class TestReadTestFiles:
    """Test file reading and concatenation."""

    def test_reads_files(self):
        """Test reading and concatenating test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, "test_a.py")
            f2 = os.path.join(tmpdir, "test_b.py")
            with open(f1, "w") as f:
                f.write("def test_a():\n    assert True\n")
            with open(f2, "w") as f:
                f.write("def test_b():\n    assert True\n")

            content = _read_test_files([f1, f2])
            assert "test_a.py" in content
            assert "test_b.py" in content
            assert "def test_a" in content
            assert "def test_b" in content

    def test_respects_max_chars(self):
        """Test that output is truncated at max_chars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_big.py")
            with open(path, "w") as f:
                f.write("x = 1\n" * 10000)

            content = _read_test_files([path], max_chars=500)
            assert len(content) <= 600  # Allow some overhead for header

    def test_skips_missing_files(self):
        """Test that missing files are skipped."""
        content = _read_test_files(["/nonexistent/test_x.py"])
        assert content == ""


class TestRunAdversarialReview:
    """Test the adversarial review execution."""

    @patch("src.verification.adversarial_review.subprocess.run")
    def test_successful_review(self, mock_run):
        """Test successful claude CLI call with issues found."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ISSUE: test_x.py::test_foo — bad assertion\n",
            stderr=""
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_x.py")
            with open(path, "w") as f:
                f.write("def test_foo():\n    assert True\n")

            issues, output, error = run_adversarial_review([path])
            assert len(issues) == 1
            assert error is None
            assert mock_run.called

    @patch("src.verification.adversarial_review.subprocess.run")
    def test_no_issues_review(self, mock_run):
        """Test claude CLI call with no issues."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NO_ISSUES_FOUND\n",
            stderr=""
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_x.py")
            with open(path, "w") as f:
                f.write("def test_foo():\n    assert 1 == 1\n")

            issues, output, error = run_adversarial_review([path])
            assert len(issues) == 0
            assert error is None

    @patch("src.verification.adversarial_review.subprocess.run")
    def test_cli_failure(self, mock_run):
        """Test handling of non-zero exit code."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: model not available"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_x.py")
            with open(path, "w") as f:
                f.write("def test_foo():\n    assert True\n")

            issues, output, error = run_adversarial_review([path])
            assert len(issues) == 0
            assert error is not None
            assert "exited with code 1" in error

    @patch("src.verification.adversarial_review.subprocess.run",
           side_effect=FileNotFoundError("claude not found"))
    def test_cli_not_found(self, mock_run):
        """Test handling when claude CLI is not installed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_x.py")
            with open(path, "w") as f:
                f.write("def test_foo():\n    assert True\n")

            issues, output, error = run_adversarial_review([path])
            assert error == "claude CLI not found on PATH"

    @patch("src.verification.adversarial_review.subprocess.run",
           side_effect=__import__("subprocess").TimeoutExpired(cmd="claude", timeout=120))
    def test_cli_timeout(self, mock_run):
        """Test handling of timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_x.py")
            with open(path, "w") as f:
                f.write("def test_foo():\n    assert True\n")

            issues, output, error = run_adversarial_review([path])
            assert "timed out" in error

    def test_empty_file_list(self):
        """Test with empty file list."""
        issues, output, error = run_adversarial_review([])
        assert len(issues) == 0
        assert error is None


class TestAdversarialReviewLayer:
    """Test the L7 AdversarialReviewLayer."""

    def test_layer_properties(self):
        """Test layer name and level."""
        layer = AdversarialReviewLayer()
        assert layer.name == "AdversarialReview"
        assert layer.level == 70

    def test_no_files_passes(self):
        """Test that no test files returns pass."""
        layer = AdversarialReviewLayer()
        result = layer.run(test_files=None)
        assert result.passed is True
        assert "no test files" in result.message.lower()

    @patch("src.verification.adversarial_review.subprocess.run")
    def test_issues_found_advisory(self, mock_run):
        """Test that issues are reported but layer still passes."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ISSUE: test_x.py::test_foo — hardcoded return\n",
            stderr=""
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_x.py")
            with open(path, "w") as f:
                f.write("def test_foo():\n    assert True\n")

            layer = AdversarialReviewLayer()
            result = layer.run(test_files=[path])
            assert result.passed is True  # Advisory
            assert "1 issue" in result.message
            assert len(result.error_details) > 0

    @patch("src.verification.adversarial_review.subprocess.run",
           side_effect=FileNotFoundError())
    def test_error_still_passes(self, mock_run):
        """Test that errors don't block pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_x.py")
            with open(path, "w") as f:
                f.write("def test_foo():\n    assert True\n")

            layer = AdversarialReviewLayer()
            result = layer.run(test_files=[path])
            assert result.passed is True
            assert "skipped" in result.message.lower()

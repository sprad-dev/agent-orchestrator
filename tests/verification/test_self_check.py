"""Tests for self_check module.

Tests the dogfood verification pipeline that runs against the agent-orchestrator
itself, including file change detection, language detection, and verification
runner invocation.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from subprocess import CalledProcessError

from src.verification.self_check import get_changed_files, run_self_check
from src.verification.language_detector import Language


class TestGetChangedFiles:
    """Test get_changed_files function."""

    def test_get_changed_files_returns_py_files(self):
        """Test that only .py files are returned, excluding __pycache__."""
        mock_output = """src/models/architect.py
src/models/intern.py
README.md
src/verification/__pycache__/runner.py
docs/setup.sh
tests/verification/test_runner.py"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
            result = get_changed_files("HEAD~1")

        expected = [
            "src/models/architect.py",
            "src/models/intern.py",
            "tests/verification/test_runner.py"
        ]
        assert result == expected
        mock_run.assert_called_once_with(
            ["git", "diff", "--name-only", "HEAD~1"],
            capture_output=True,
            text=True,
            check=True
        )

    def test_get_changed_files_filters_pycache(self):
        """Test that __pycache__ files are excluded."""
        mock_output = """src/module.py
src/__pycache__/module.cpython-39.pyc
src/verification/__pycache__/runner.py
other/__pycache__/file.py"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
            result = get_changed_files("HEAD~1")

        assert result == ["src/module.py"]

    def test_get_changed_files_custom_diff_ref(self):
        """Test that custom diff_ref is passed to git command."""
        mock_output = """src/file.py"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
            result = get_changed_files("origin/main")

        mock_run.assert_called_once_with(
            ["git", "diff", "--name-only", "origin/main"],
            capture_output=True,
            text=True,
            check=True
        )

    def test_get_changed_files_empty_on_error(self):
        """Test that empty list is returned on git command error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = CalledProcessError(1, "git diff")
            result = get_changed_files("HEAD~1")

        assert result == []

    def test_get_changed_files_empty_output(self):
        """Test that empty string output returns empty list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            result = get_changed_files("HEAD~1")

        assert result == []

    def test_get_changed_files_only_non_py_files(self):
        """Test that list is empty when no .py files in output."""
        mock_output = """README.md
docs/guide.txt
src/config.yaml"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
            result = get_changed_files("HEAD~1")

        assert result == []

    def test_get_changed_files_with_whitespace(self):
        """Test that whitespace is handled correctly."""
        # Output includes leading/trailing whitespace
        mock_output = """
src/module.py
src/utils.py

"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
            result = get_changed_files("HEAD~1")

        # Empty strings from split should be filtered out
        assert "src/module.py" in result
        assert "src/utils.py" in result


class TestRunSelfCheck:
    """Test run_self_check function."""

    def test_run_self_check_passes(self):
        """Test that run_self_check returns True when verification passes."""
        mock_files = ["src/models/architect.py", "src/shell/__init__.py"]

        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print"):

            mock_get_files.return_value = mock_files
            mock_detect.return_value = Language.PYTHON

            # Mock the VerificationRunner instance
            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "All checks passed")
            mock_runner_class.return_value = mock_runner_instance

            result = run_self_check(verify_cmd="pytest", diff_ref="HEAD~1", project_path=".")

        assert result is True
        mock_runner_instance.run.assert_called_once_with(modified_files=mock_files)

    def test_run_self_check_fails(self):
        """Test that run_self_check returns False when verification fails."""
        mock_files = ["src/module.py"]

        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print"):

            mock_get_files.return_value = mock_files
            mock_detect.return_value = Language.PYTHON

            # Mock the VerificationRunner instance to return failure
            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (False, "Syntax error in src/module.py")
            mock_runner_class.return_value = mock_runner_instance

            result = run_self_check(verify_cmd="pytest", diff_ref="HEAD~1", project_path=".")

        assert result is False
        mock_runner_instance.run.assert_called_once_with(modified_files=mock_files)

    def test_run_self_check_no_changed_files(self):
        """Test that runner.run is called with None when no changed files."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print"):

            mock_get_files.return_value = []
            mock_detect.return_value = Language.PYTHON

            # Mock the VerificationRunner instance
            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "Tests passed")
            mock_runner_class.return_value = mock_runner_instance

            result = run_self_check(verify_cmd="pytest", diff_ref="HEAD~1", project_path=".")

        # When no changed files, modified_files should be None
        mock_runner_instance.run.assert_called_once_with(modified_files=None)

    def test_run_self_check_custom_verify_cmd(self):
        """Test that custom verify_cmd is passed to VerificationRunner."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print"):

            mock_get_files.return_value = ["src/file.py"]
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "OK")
            mock_runner_class.return_value = mock_runner_instance

            run_self_check(verify_cmd="nose", diff_ref="HEAD~1", project_path=".")

        # Verify verify_cmd was passed; config is also passed now
        call_kwargs = mock_runner_class.call_args[1]
        assert call_kwargs["verify_cmd"] == "nose"
        assert call_kwargs["config"].test_command == "nose"

    def test_run_self_check_custom_diff_ref(self):
        """Test that custom diff_ref is passed to get_changed_files."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print"):

            mock_get_files.return_value = []
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "OK")
            mock_runner_class.return_value = mock_runner_instance

            run_self_check(verify_cmd="pytest", diff_ref="origin/main", project_path=".")

        mock_get_files.assert_called_once_with("origin/main")

    def test_run_self_check_custom_project_path(self):
        """Test that custom project_path is passed to detect_language."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print"):

            mock_get_files.return_value = []
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "OK")
            mock_runner_class.return_value = mock_runner_instance

            run_self_check(verify_cmd="pytest", diff_ref="HEAD~1", project_path="/custom/path")

        mock_detect.assert_called_once_with("/custom/path")

    def test_language_detection_runs(self):
        """Test that language detection is called with project_path."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print"):

            mock_get_files.return_value = []
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "OK")
            mock_runner_class.return_value = mock_runner_instance

            project_path = "/home/user/project"
            run_self_check(project_path=project_path)

        mock_detect.assert_called_once_with(project_path)

    def test_language_detection_unknown(self):
        """Test handling when language detection returns UNKNOWN."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print") as mock_print:

            mock_get_files.return_value = []
            mock_detect.return_value = Language.UNKNOWN

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "OK")
            mock_runner_class.return_value = mock_runner_instance

            result = run_self_check()

        assert result is True
        # Verify that warning message was printed
        warning_calls = [c for c in mock_print.call_args_list
                        if len(c[0]) > 0 and "WARNING" in str(c[0][0])]
        assert len(warning_calls) > 0

    def test_run_self_check_prints_output(self):
        """Test that verification runner output is printed."""
        test_output = "Layer 1: PASS\nLayer 2: PASS"

        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print") as mock_print:

            mock_get_files.return_value = ["src/file.py"]
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, test_output)
            mock_runner_class.return_value = mock_runner_instance

            run_self_check()

        # Verify that output was printed
        output_calls = [c for c in mock_print.call_args_list
                       if len(c[0]) > 0 and "Layer" in str(c[0][0])]
        assert len(output_calls) > 0

    def test_run_self_check_prints_pass_message(self):
        """Test that PASS message is printed on success."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print") as mock_print:

            mock_get_files.return_value = []
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "")
            mock_runner_class.return_value = mock_runner_instance

            result = run_self_check()

        assert result is True
        # Verify PASS message was printed
        pass_calls = [c for c in mock_print.call_args_list
                     if len(c[0]) > 0 and "PASS" in str(c[0][0])]
        assert len(pass_calls) > 0

    def test_run_self_check_prints_fail_message(self):
        """Test that FAIL message is printed on failure."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print") as mock_print:

            mock_get_files.return_value = []
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (False, "")
            mock_runner_class.return_value = mock_runner_instance

            result = run_self_check()

        assert result is False
        # Verify FAIL message was printed
        fail_calls = [c for c in mock_print.call_args_list
                     if len(c[0]) > 0 and "FAIL" in str(c[0][0])]
        assert len(fail_calls) > 0

    def test_run_self_check_prints_changed_files_summary(self):
        """Test that summary of changed files is printed."""
        mock_files = ["src/file1.py", "src/file2.py"]

        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print") as mock_print:

            mock_get_files.return_value = mock_files
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "")
            mock_runner_class.return_value = mock_runner_instance

            run_self_check()

        # Verify that changed files count was printed
        file_calls = [c for c in mock_print.call_args_list
                     if len(c[0]) > 0 and "Changed files" in str(c[0][0])]
        assert len(file_calls) > 0

    def test_run_self_check_prints_no_changes_message(self):
        """Test that message is printed when no files changed."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print") as mock_print:

            mock_get_files.return_value = []
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "")
            mock_runner_class.return_value = mock_runner_instance

            run_self_check(diff_ref="HEAD~1")

        # Verify that "no changed files" message was printed
        no_change_calls = [c for c in mock_print.call_args_list
                          if len(c[0]) > 0 and "No changed" in str(c[0][0])]
        assert len(no_change_calls) > 0

    def test_run_self_check_truncates_long_file_list(self):
        """Test that long file lists are truncated in output."""
        # Create 15 files to test truncation at 10
        mock_files = [f"src/file{i}.py" for i in range(15)]

        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print") as mock_print:

            mock_get_files.return_value = mock_files
            mock_detect.return_value = Language.PYTHON

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "")
            mock_runner_class.return_value = mock_runner_instance

            run_self_check()

        # Verify that "and X more" message was printed
        more_calls = [c for c in mock_print.call_args_list
                     if len(c[0]) > 0 and "more" in str(c[0][0])]
        assert len(more_calls) > 0

    def test_run_self_check_prints_language_name(self):
        """Test that detected language is printed."""
        with patch("src.verification.self_check.get_changed_files") as mock_get_files, \
             patch("src.verification.self_check.detect_language") as mock_detect, \
             patch("src.verification.self_check.VerificationRunner") as mock_runner_class, \
             patch("builtins.print") as mock_print:

            mock_get_files.return_value = []
            mock_detect.return_value = Language.TYPESCRIPT

            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = (True, "")
            mock_runner_class.return_value = mock_runner_instance

            run_self_check()

        # Verify that language was printed
        lang_calls = [c for c in mock_print.call_args_list
                     if len(c[0]) > 0 and "typescript" in str(c[0][0]).lower()]
        assert len(lang_calls) > 0

#!/usr/bin/env python3
"""Unit tests for src/shell/executor.py module.

Tests all shell command execution and git operations functions.
"""

import unittest
from unittest.mock import patch, MagicMock
import subprocess
from src.shell.executor import (
    run_shell,
    has_changes,
    get_diff_summary,
    get_diff_content,
    truncate_error,
    build_agent_command,
)


class TestRunShell(unittest.TestCase):
    """Tests for run_shell function."""

    @patch('subprocess.run')
    def test_run_shell_success(self, mock_run):
        """Test successful command execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "success output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        success, output, returncode = run_shell("echo test", ignore_error=False)

        self.assertTrue(success)
        self.assertEqual(output, "success output")
        self.assertEqual(returncode, 0)
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_run_shell_failure(self, mock_run):
        """Test failed command execution."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd="false",
            output="",
            stderr="error message"
        )

        success, output, returncode = run_shell("false", ignore_error=False)

        self.assertFalse(success)
        self.assertEqual(returncode, 1)
        self.assertIn("error message", output)

    @patch('subprocess.run')
    def test_run_shell_timeout(self, mock_run):
        """Test command timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="sleep 10",
            timeout=2,
            output=b"partial output",
            stderr=b"partial error"
        )

        success, output, returncode = run_shell("sleep 10", ignore_error=True, timeout=2)

        self.assertFalse(success)
        self.assertEqual(returncode, -1)
        self.assertIn("TIMEOUT", output)
        self.assertIn("partial output", output)
        self.assertIn("partial error", output)

    @patch('subprocess.run')
    def test_run_shell_ignore_error_true(self, mock_run):
        """Test that ignore_error=True prevents raising on non-zero exit."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "output"
        mock_result.stderr = "error"
        mock_run.return_value = mock_result

        success, output, returncode = run_shell("false", ignore_error=True)

        self.assertFalse(success)
        self.assertEqual(returncode, 1)
        # Should not raise exception
        mock_run.assert_called_once_with(
            "false",
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=None
        )

    @patch('subprocess.run')
    def test_run_shell_timeout_none_bytes(self, mock_run):
        """Test timeout with None bytes in stdout/stderr."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="sleep 10",
            timeout=2,
            output=None,
            stderr=None
        )

        success, output, returncode = run_shell("sleep 10", ignore_error=True, timeout=2)

        self.assertFalse(success)
        self.assertEqual(returncode, -1)
        self.assertIn("TIMEOUT", output)


class TestHasChanges(unittest.TestCase):
    """Tests for has_changes function."""

    @patch('src.shell.executor.run_shell')
    def test_has_changes_with_changes(self, mock_run_shell):
        """Test has_changes returns True when changes exist."""
        mock_run_shell.return_value = (True, " M file.py\n?? new.py\n", 0)

        result = has_changes()

        self.assertTrue(result)
        mock_run_shell.assert_called_once_with("git status --porcelain", ignore_error=True)

    @patch('src.shell.executor.run_shell')
    def test_has_changes_without_changes(self, mock_run_shell):
        """Test has_changes returns False when no changes exist."""
        mock_run_shell.return_value = (True, "", 0)

        result = has_changes()

        self.assertFalse(result)

    @patch('src.shell.executor.run_shell')
    def test_has_changes_with_whitespace(self, mock_run_shell):
        """Test has_changes handles whitespace correctly."""
        mock_run_shell.return_value = (True, "   \n  \n", 0)

        result = has_changes()

        self.assertFalse(result)

    @patch('src.shell.executor.run_shell')
    def test_has_changes_git_failure(self, mock_run_shell):
        """Test has_changes returns False when git command fails."""
        mock_run_shell.return_value = (False, "fatal: not a git repository", 128)

        result = has_changes()

        self.assertFalse(result)


class TestGetDiffSummary(unittest.TestCase):
    """Tests for get_diff_summary function."""

    @patch('src.shell.executor.run_shell')
    def test_get_diff_summary_success(self, mock_run_shell):
        """Test get_diff_summary returns diff stat output."""
        expected_output = " file.py | 10 +++++-----\n 1 file changed, 5 insertions(+), 5 deletions(-)"
        mock_run_shell.return_value = (True, expected_output, 0)

        result = get_diff_summary()

        self.assertEqual(result, expected_output)
        mock_run_shell.assert_called_once_with("git diff --stat", ignore_error=True)

    @patch('src.shell.executor.run_shell')
    def test_get_diff_summary_failure(self, mock_run_shell):
        """Test get_diff_summary returns error message on failure."""
        mock_run_shell.return_value = (False, "fatal: error", 1)

        result = get_diff_summary()

        self.assertEqual(result, "Unable to get diff")


class TestGetDiffContent(unittest.TestCase):
    """Tests for get_diff_content function."""

    @patch('src.shell.executor.run_shell')
    def test_get_diff_content_success(self, mock_run_shell):
        """Test get_diff_content returns full diff output."""
        expected_diff = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py"
        mock_run_shell.return_value = (True, expected_diff, 0)

        result = get_diff_content()

        self.assertEqual(result, expected_diff)
        mock_run_shell.assert_called_once_with("git diff", ignore_error=True)

    @patch('src.shell.executor.run_shell')
    def test_get_diff_content_failure(self, mock_run_shell):
        """Test get_diff_content returns error message on failure."""
        mock_run_shell.return_value = (False, "fatal: error", 1)

        result = get_diff_content()

        self.assertEqual(result, "Unable to get diff")


class TestTruncateError(unittest.TestCase):
    """Tests for truncate_error function."""

    def test_truncate_error_short_text(self):
        """Test that short text is not truncated."""
        short_text = "This is a short error message"
        result = truncate_error(short_text, max_length=2000)
        self.assertEqual(result, short_text)

    def test_truncate_error_long_text(self):
        """Test that long text is truncated correctly."""
        long_text = "X" * 5000
        result = truncate_error(long_text, max_length=2000)

        # Should have first chunk, truncation notice, and last chunk
        self.assertIn("X", result)
        self.assertIn("truncated", result)
        self.assertLess(len(result), 5000)

        # First 1000 chars should be 'X'
        self.assertTrue(result.startswith("X" * 1000))
        # Last 1000 chars should be 'X'
        self.assertTrue(result.endswith("X" * 1000))

    def test_truncate_error_exact_max_length(self):
        """Test text exactly at max_length is not truncated."""
        text = "A" * 2000
        result = truncate_error(text, max_length=2000)
        self.assertEqual(result, text)

    def test_truncate_error_one_over_max(self):
        """Test text one character over max is truncated."""
        text = "B" * 2001
        result = truncate_error(text, max_length=2000)
        self.assertNotEqual(result, text)
        self.assertIn("truncated", result)

    def test_truncate_error_empty_string(self):
        """Test empty string handling."""
        result = truncate_error("", max_length=2000)
        self.assertEqual(result, "")

    def test_truncate_error_none(self):
        """Test None handling."""
        result = truncate_error(None, max_length=2000)
        self.assertIsNone(result)

    def test_truncate_error_custom_max_length(self):
        """Test custom max_length parameter."""
        text = "Z" * 1000
        result = truncate_error(text, max_length=500)

        self.assertLess(len(result), 1000)
        self.assertIn("truncated", result)
        # Should have ~250 chars from start and ~250 from end
        self.assertTrue(result.startswith("Z" * 250))
        self.assertTrue(result.endswith("Z" * 250))

    def test_truncate_error_truncation_message(self):
        """Test that truncation message includes correct character count."""
        text = "M" * 3000
        result = truncate_error(text, max_length=2000)

        # Should truncate 1000 chars (3000 - 2000)
        self.assertIn("truncated 1000 chars", result)


class TestBuildAgentCommand(unittest.TestCase):
    """Tests for build_agent_command function."""

    def test_build_agent_command_basic(self):
        """Test basic command building with prompt and model substitution."""
        template = "claude {prompt} --model={model}"
        prompt = "Fix the bug"
        model = "sonnet"

        result = build_agent_command(template, prompt, model)

        self.assertIn("claude", result)
        self.assertIn("sonnet", result)
        # Prompt should be quoted
        self.assertIn("'Fix the bug'", result)

    def test_build_agent_command_special_characters(self):
        """Test that special characters in prompt are escaped."""
        template = "./agent.sh {prompt} {model}"
        prompt = "Fix bug with 'quotes' and $variables"
        model = "haiku"

        result = build_agent_command(template, prompt, model)

        # shlex.quote should escape the prompt safely
        self.assertIn("./agent.sh", result)
        self.assertIn("haiku", result)
        # Original prompt text should be present but safely quoted
        self.assertIn("Fix bug", result)

    def test_build_agent_command_multiline_prompt(self):
        """Test handling of multiline prompts."""
        template = "echo {prompt}"
        prompt = "Line 1\nLine 2\nLine 3"
        model = "test"

        result = build_agent_command(template, prompt, model)

        self.assertIn("echo", result)
        # Multiline should be quoted as a single argument
        self.assertIn("Line 1", result)

    def test_build_agent_command_empty_prompt(self):
        """Test handling of empty prompt."""
        template = "agent {prompt} --model {model}"
        prompt = ""
        model = "model1"

        result = build_agent_command(template, prompt, model)

        # Empty string should be quoted as ''
        self.assertIn("''", result)
        self.assertIn("model1", result)

    def test_build_agent_command_no_placeholders(self):
        """Test template with no placeholders."""
        template = "static-command"
        prompt = "test prompt"
        model = "test-model"

        result = build_agent_command(template, prompt, model)

        # Should return template unchanged
        self.assertEqual(result, "static-command")

    def test_build_agent_command_only_model_placeholder(self):
        """Test template with only model placeholder."""
        template = "agent --model={model}"
        prompt = "test"
        model = "haiku"

        result = build_agent_command(template, prompt, model)

        self.assertEqual(result, "agent --model=haiku")

    def test_build_agent_command_only_prompt_placeholder(self):
        """Test template with only prompt placeholder."""
        template = "echo {prompt}"
        prompt = "hello world"
        model = "unused"

        result = build_agent_command(template, prompt, model)

        self.assertIn("'hello world'", result)

    def test_build_agent_command_multiple_placeholders(self):
        """Test template with multiple occurrences of same placeholder."""
        template = "cmd {prompt} --text={prompt} --model={model}"
        prompt = "test"
        model = "m1"

        result = build_agent_command(template, prompt, model)

        # Both {prompt} should be replaced (shlex.quote may or may not add quotes for simple strings)
        self.assertEqual(result.count("test"), 2)
        self.assertIn("m1", result)

    def test_build_agent_command_shell_injection_protection(self):
        """Test that command injection attempts are escaped."""
        template = "agent {prompt}"
        prompt = "; rm -rf / #"
        model = "test"

        result = build_agent_command(template, prompt, model)

        # The dangerous prompt should be safely quoted
        # shlex.quote will handle this - verify the result is a single quoted string
        self.assertIn("agent", result)
        # The semicolon should be within quotes, not executing as separate command
        self.assertNotEqual(result, "agent ; rm -rf / #")


if __name__ == "__main__":
    unittest.main()

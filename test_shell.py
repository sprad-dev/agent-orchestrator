#!/usr/bin/env python3
"""Unit tests for src/shell/executor.py module.

Tests all shell command execution and git operations functions.
"""

import unittest
from unittest.mock import patch, MagicMock
import subprocess
from src.shell.executor import (
    run_shell,
    run_shell_with_retry,
    _is_transient_failure,
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


class TestIsTransientFailure(unittest.TestCase):
    """Tests for _is_transient_failure function."""

    def test_timeout_is_transient(self):
        """Test that timeout (returncode -1) is detected as transient."""
        result = _is_transient_failure(-1, "Command timed out")
        self.assertTrue(result)

    def test_connection_refused_is_transient(self):
        """Test that connection refused errors are detected as transient."""
        result = _is_transient_failure(1, "Error: connection refused")
        self.assertTrue(result)

    def test_connection_reset_is_transient(self):
        """Test that connection reset errors are detected as transient."""
        result = _is_transient_failure(1, "connection reset by peer")
        self.assertTrue(result)

    def test_rate_limit_429_is_transient(self):
        """Test that 429 rate limit errors are detected as transient."""
        result = _is_transient_failure(1, "HTTP 429 Too Many Requests")
        self.assertTrue(result)

    def test_service_unavailable_503_is_transient(self):
        """Test that 503 service unavailable errors are detected as transient."""
        result = _is_transient_failure(1, "HTTP 503 Service Unavailable")
        self.assertTrue(result)

    def test_network_timeout_is_transient(self):
        """Test that network timeout errors are detected as transient."""
        result = _is_transient_failure(1, "network error: timed out")
        self.assertTrue(result)

    def test_dns_error_is_transient(self):
        """Test that DNS errors are detected as transient."""
        result = _is_transient_failure(1, "Could not resolve host: example.com")
        self.assertTrue(result)

    def test_temporary_unavailability_is_transient(self):
        """Test that temporary unavailability is detected as transient."""
        result = _is_transient_failure(1, "Service temporarily unavailable")
        self.assertTrue(result)

    def test_non_transient_error(self):
        """Test that non-transient errors are not flagged."""
        result = _is_transient_failure(1, "Syntax error in file.py")
        self.assertFalse(result)

    def test_case_insensitive_detection(self):
        """Test that error detection is case-insensitive."""
        result = _is_transient_failure(1, "CONNECTION REFUSED")
        self.assertTrue(result)

    def test_success_not_transient(self):
        """Test that success (returncode 0) is not transient."""
        result = _is_transient_failure(0, "Success output")
        self.assertFalse(result)


class TestRunShellWithRetry(unittest.TestCase):
    """Tests for run_shell_with_retry function."""

    @patch('src.shell.executor.run_shell')
    def test_success_first_attempt(self, mock_run_shell):
        """Test that success on first attempt returns immediately without retries."""
        mock_run_shell.return_value = (True, "success", 0)

        success, output, returncode = run_shell_with_retry(
            "echo test",
            max_retries=3
        )

        self.assertTrue(success)
        self.assertEqual(output, "success")
        self.assertEqual(returncode, 0)
        # Should only call once (no retries needed)
        self.assertEqual(mock_run_shell.call_count, 1)

    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_success_after_retry(self, mock_run_shell, mock_sleep):
        """Test success after transient failure and retry."""
        # First call: transient failure (timeout)
        # Second call: success
        mock_run_shell.side_effect = [
            (False, "Command timed out", -1),
            (True, "success", 0)
        ]

        success, output, returncode = run_shell_with_retry(
            "claude 'test'",
            max_retries=3,
            initial_delay=1.0,
            jitter=False
        )

        self.assertTrue(success)
        self.assertEqual(output, "success")
        self.assertEqual(returncode, 0)
        # Should call twice (1 failure + 1 success)
        self.assertEqual(mock_run_shell.call_count, 2)
        # Should sleep once between attempts
        mock_sleep.assert_called_once()

    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_non_transient_failure_no_retry(self, mock_run_shell, mock_sleep):
        """Test that non-transient failures don't trigger retries."""
        mock_run_shell.return_value = (False, "Syntax error", 1)

        success, output, returncode = run_shell_with_retry(
            "python bad_code.py",
            max_retries=3
        )

        self.assertFalse(success)
        self.assertEqual(output, "Syntax error")
        self.assertEqual(returncode, 1)
        # Should only call once (no retries for non-transient)
        self.assertEqual(mock_run_shell.call_count, 1)
        # Should not sleep
        mock_sleep.assert_not_called()

    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_exhaust_max_retries(self, mock_run_shell, mock_sleep):
        """Test that retries stop after max_retries is exhausted."""
        # All calls fail with transient error
        mock_run_shell.return_value = (False, "connection refused", 1)

        success, output, returncode = run_shell_with_retry(
            "agent command",
            max_retries=3,
            jitter=False
        )

        self.assertFalse(success)
        self.assertIn("connection refused", output)
        # Should call: initial attempt + 3 retries = 4 total
        self.assertEqual(mock_run_shell.call_count, 4)
        # Should sleep 3 times (after each failed retry)
        self.assertEqual(mock_sleep.call_count, 3)

    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_exponential_backoff(self, mock_run_shell, mock_sleep):
        """Test that exponential backoff delays increase correctly."""
        # All calls fail with transient error
        mock_run_shell.return_value = (False, "timeout", -1)

        run_shell_with_retry(
            "agent command",
            max_retries=3,
            initial_delay=2.0,
            backoff_multiplier=2.0,
            jitter=False
        )

        # Should sleep with delays: 2.0, 4.0, 8.0
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(len(sleep_calls), 3)
        self.assertEqual(sleep_calls[0], 2.0)
        self.assertEqual(sleep_calls[1], 4.0)
        self.assertEqual(sleep_calls[2], 8.0)

    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_max_delay_cap(self, mock_run_shell, mock_sleep):
        """Test that delays are capped at max_delay."""
        mock_run_shell.return_value = (False, "rate limit", 1)

        run_shell_with_retry(
            "agent command",
            max_retries=5,
            initial_delay=10.0,
            backoff_multiplier=3.0,
            max_delay=20.0,
            jitter=False
        )

        # Delays without cap would be: 10, 30, 90, 270, 810
        # With max_delay=20, should be: 10, 20, 20, 20, 20
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(len(sleep_calls), 5)
        self.assertEqual(sleep_calls[0], 10.0)
        self.assertEqual(sleep_calls[1], 20.0)  # Capped
        self.assertEqual(sleep_calls[2], 20.0)  # Capped
        self.assertEqual(sleep_calls[3], 20.0)  # Capped
        self.assertEqual(sleep_calls[4], 20.0)  # Capped

    @patch('random.random')
    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_jitter_enabled(self, mock_run_shell, mock_sleep, mock_random):
        """Test that jitter adds randomness to delays."""
        mock_run_shell.return_value = (False, "timeout", -1)
        mock_random.return_value = 0.75  # Will result in 0.5 + 0.75 = 1.25 multiplier

        run_shell_with_retry(
            "agent command",
            max_retries=2,
            initial_delay=10.0,
            backoff_multiplier=2.0,
            jitter=True
        )

        # First retry: 10.0 * 1.25 = 12.5
        # Second retry: 20.0 * 1.25 = 25.0
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(len(sleep_calls), 2)
        self.assertAlmostEqual(sleep_calls[0], 12.5)
        self.assertAlmostEqual(sleep_calls[1], 25.0)

    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_ignore_error_with_retries(self, mock_run_shell, mock_sleep):
        """Test ignore_error=True still allows retries for transient failures."""
        mock_run_shell.side_effect = [
            (False, "429 rate limit", 1),
            (True, "success", 0)
        ]

        success, output, returncode = run_shell_with_retry(
            "agent command",
            ignore_error=True,
            max_retries=3,
            jitter=False
        )

        self.assertTrue(success)
        self.assertEqual(mock_run_shell.call_count, 2)
        mock_sleep.assert_called_once()

    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_timeout_parameter_passed(self, mock_run_shell, mock_sleep):
        """Test that timeout parameter is passed to run_shell."""
        mock_run_shell.return_value = (True, "success", 0)

        run_shell_with_retry(
            "agent command",
            timeout=300,
            max_retries=3
        )

        # Verify timeout was passed to run_shell
        mock_run_shell.assert_called_once()
        call_kwargs = mock_run_shell.call_args[1]
        self.assertEqual(call_kwargs['timeout'], 300)

    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_zero_retries(self, mock_run_shell, mock_sleep):
        """Test that max_retries=0 means no retries (single attempt only)."""
        mock_run_shell.return_value = (False, "timeout", -1)

        success, output, returncode = run_shell_with_retry(
            "agent command",
            max_retries=0
        )

        self.assertFalse(success)
        # Should only call once (no retries)
        self.assertEqual(mock_run_shell.call_count, 1)
        # Should not sleep
        mock_sleep.assert_not_called()

    @patch('time.sleep')
    @patch('src.shell.executor.run_shell')
    def test_multiple_transient_patterns(self, mock_run_shell, mock_sleep):
        """Test detection of various transient failure patterns."""
        transient_errors = [
            "connection refused",
            "503 service unavailable",
            "network error occurred",
            "failed to connect",
        ]

        for error_msg in transient_errors:
            mock_run_shell.reset_mock()
            mock_sleep.reset_mock()
            mock_run_shell.side_effect = [
                (False, error_msg, 1),
                (True, "success", 0)
            ]

            success, output, returncode = run_shell_with_retry(
                "test",
                max_retries=3,
                jitter=False
            )

            self.assertTrue(success, f"Failed to retry for: {error_msg}")
            self.assertEqual(mock_run_shell.call_count, 2)
            mock_sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()

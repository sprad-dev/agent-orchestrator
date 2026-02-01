#!/usr/bin/env python3
"""Unit tests for src/preconditions/checks.py module.

Tests all precondition check functions.
"""

import unittest
from unittest.mock import patch, MagicMock
from src.preconditions.checks import (
    check_git_clean,
    check_tests_exist,
    check_agent_reachable,
)


class TestCheckGitClean(unittest.TestCase):
    """Tests for check_git_clean function."""

    @patch('src.preconditions.checks.run_shell')
    def test_check_git_clean_when_clean(self, mock_run_shell):
        """Test check passes when working tree is clean."""
        mock_run_shell.return_value = (True, "", 0)

        passed, message = check_git_clean()

        self.assertTrue(passed)
        self.assertEqual(message, "Working tree is clean")
        mock_run_shell.assert_called_once_with("git status --porcelain", ignore_error=True)

    @patch('src.preconditions.checks.run_shell')
    def test_check_git_clean_when_dirty(self, mock_run_shell):
        """Test check fails when working tree has uncommitted changes."""
        mock_run_shell.return_value = (True, " M file.py\n?? new.py\n", 0)

        passed, message = check_git_clean()

        self.assertFalse(passed)
        self.assertIn("Working tree has uncommitted changes", message)
        self.assertIn("M file.py", message)
        self.assertIn("?? new.py", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_git_clean_with_staged_changes(self, mock_run_shell):
        """Test check fails when working tree has staged changes."""
        mock_run_shell.return_value = (True, "A  staged.py\n", 0)

        passed, message = check_git_clean()

        self.assertFalse(passed)
        self.assertIn("Working tree has uncommitted changes", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_git_clean_git_command_fails(self, mock_run_shell):
        """Test check fails when git status command fails."""
        mock_run_shell.return_value = (False, "fatal: not a git repository", 128)

        passed, message = check_git_clean()

        self.assertFalse(passed)
        self.assertEqual(message, "Failed to check git status")

    @patch('src.preconditions.checks.run_shell')
    def test_check_git_clean_with_whitespace_only(self, mock_run_shell):
        """Test check passes when output is only whitespace."""
        mock_run_shell.return_value = (True, "   \n  \n", 0)

        passed, message = check_git_clean()

        self.assertTrue(passed)
        self.assertEqual(message, "Working tree is clean")

    @patch('src.preconditions.checks.run_shell')
    def test_check_git_clean_truncates_long_output(self, mock_run_shell):
        """Test that long git status output is truncated."""
        long_output = "M file.py\n" * 1000  # Very long output
        mock_run_shell.return_value = (True, long_output, 0)

        passed, message = check_git_clean()

        self.assertFalse(passed)
        # Message should be truncated
        self.assertLess(len(message), len(long_output) + 100)


class TestCheckTestsExist(unittest.TestCase):
    """Tests for check_tests_exist function."""

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_with_pytest(self, mock_run_shell):
        """Test check passes when pytest collects tests."""
        mock_run_shell.return_value = (True, "collected 5 tests\n", 0)

        passed, message = check_tests_exist("pytest")

        self.assertTrue(passed)
        self.assertIn("Collected 5 test", message)
        mock_run_shell.assert_called_once_with("pytest --collect-only -q", ignore_error=True)

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_with_pytest_module(self, mock_run_shell):
        """Test check works with 'python -m pytest' syntax."""
        mock_run_shell.return_value = (True, "collected 3 tests\n", 0)

        passed, message = check_tests_exist("python -m pytest")

        self.assertTrue(passed)
        self.assertIn("Collected 3 test", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_zero_tests(self, mock_run_shell):
        """Test check fails when pytest collects 0 items."""
        mock_run_shell.return_value = (True, "collected 0 items\n", 0)

        passed, message = check_tests_exist("pytest")

        self.assertFalse(passed)
        self.assertIn("No tests collected", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_no_tests_collected(self, mock_run_shell):
        """Test check fails with 'no tests collected' message."""
        mock_run_shell.return_value = (False, "ERROR: no tests collected\n", 1)

        passed, message = check_tests_exist("pytest")

        self.assertFalse(passed)
        self.assertIn("No tests collected", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_skip_non_pytest(self, mock_run_shell):
        """Test check skips for non-pytest commands."""
        passed, message = check_tests_exist("./custom-verifier.sh")

        self.assertTrue(passed)
        self.assertIn("Skipping test collection check", message)
        # Should not call run_shell at all
        mock_run_shell.assert_not_called()

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_skip_npm_test(self, mock_run_shell):
        """Test check skips for npm test commands."""
        passed, message = check_tests_exist("npm test")

        self.assertTrue(passed)
        self.assertIn("Skipping test collection check", message)
        mock_run_shell.assert_not_called()

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_handles_pytest_failure(self, mock_run_shell):
        """Test check handles pytest collection failures gracefully."""
        mock_run_shell.return_value = (
            False,
            "ImportError: cannot import name 'foo'\ncollected 0 items\n",
            1
        )

        passed, message = check_tests_exist("pytest")

        self.assertFalse(passed)
        self.assertIn("No tests collected", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_syntax_error(self, mock_run_shell):
        """Test check handles syntax errors in test files."""
        mock_run_shell.return_value = (
            False,
            "SyntaxError: invalid syntax\nno tests collected\n",
            2
        )

        passed, message = check_tests_exist("pytest")

        self.assertFalse(passed)
        self.assertIn("No tests collected", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_multiple_tests(self, mock_run_shell):
        """Test check with plural 'tests' in output."""
        mock_run_shell.return_value = (True, "collected 42 tests\n", 0)

        passed, message = check_tests_exist("pytest")

        self.assertTrue(passed)
        self.assertIn("Collected 42 test", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_one_test(self, mock_run_shell):
        """Test check with singular 'test' in output."""
        mock_run_shell.return_value = (True, "collected 1 test\n", 0)

        passed, message = check_tests_exist("pytest")

        self.assertTrue(passed)
        self.assertIn("Collected 1 test", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_generic_success(self, mock_run_shell):
        """Test check with generic success when count not parsed."""
        mock_run_shell.return_value = (True, "pytest output without count\n", 0)

        passed, message = check_tests_exist("pytest")

        self.assertTrue(passed)
        self.assertIn("Tests successfully collected", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_tests_exist_pytest_with_args(self, mock_run_shell):
        """Test check works with pytest command that has arguments."""
        mock_run_shell.return_value = (True, "collected 10 tests\n", 0)

        passed, message = check_tests_exist("pytest tests/ -v")

        self.assertTrue(passed)
        self.assertIn("Collected 10 test", message)
        # Should append --collect-only -q to the command
        mock_run_shell.assert_called_once_with("pytest tests/ -v --collect-only -q", ignore_error=True)


class TestCheckAgentReachable(unittest.TestCase):
    """Tests for check_agent_reachable function."""

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_success(self, mock_run_shell):
        """Test check passes for commands in PATH."""
        mock_run_shell.return_value = (True, "/usr/bin/echo\n", 0)

        passed, message = check_agent_reachable("echo {prompt}")

        self.assertTrue(passed)
        self.assertIn("reachable", message.lower())
        self.assertIn("echo", message)
        self.assertIn("/usr/bin/echo", message)
        mock_run_shell.assert_called_once_with("command -v echo", ignore_error=True)

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_failure(self, mock_run_shell):
        """Test check fails when command not in PATH."""
        mock_run_shell.return_value = (False, "", 1)

        passed, message = check_agent_reachable("nonexistent-command {prompt}")

        self.assertFalse(passed)
        self.assertIn("not found", message)
        self.assertIn("nonexistent-command", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_with_path(self, mock_run_shell):
        """Test check works with absolute paths."""
        mock_run_shell.return_value = (True, "/usr/local/bin/claude\n", 0)

        passed, message = check_agent_reachable("/usr/local/bin/claude {prompt}")

        self.assertTrue(passed)
        self.assertIn("claude", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_with_local_script(self, mock_run_shell):
        """Test check works with local script paths."""
        mock_run_shell.return_value = (True, "./agent.sh\n", 0)

        passed, message = check_agent_reachable("./agent.sh {prompt} {model}")

        self.assertTrue(passed)
        self.assertIn("agent.sh", message)
        mock_run_shell.assert_called_once_with("command -v ./agent.sh", ignore_error=True)

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_handles_empty_command(self, mock_run_shell):
        """Test check handles empty command template."""
        passed, message = check_agent_reachable("")

        self.assertFalse(passed)
        self.assertIn("Empty agent command", message)
        # Should not call run_shell
        mock_run_shell.assert_not_called()

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_extracts_command_name(self, mock_run_shell):
        """Test that command name is correctly extracted from template."""
        mock_run_shell.return_value = (True, "/usr/bin/python3\n", 0)

        passed, message = check_agent_reachable("python3 -m agent {prompt}")

        self.assertTrue(passed)
        self.assertIn("python3", message)
        # Should check for 'python3', not the full command string
        mock_run_shell.assert_called_once_with("command -v python3", ignore_error=True)

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_with_complex_template(self, mock_run_shell):
        """Test check with complex command template."""
        mock_run_shell.return_value = (True, "/opt/agent/bin/agent\n", 0)

        passed, message = check_agent_reachable("agent --config=cfg.yml {prompt} --model={model}")

        self.assertTrue(passed)
        self.assertIn("agent", message)
        # Should only check the first command word
        mock_run_shell.assert_called_once_with("command -v agent", ignore_error=True)

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_with_quotes_in_template(self, mock_run_shell):
        """Test check handles quotes in command template."""
        mock_run_shell.return_value = (True, "/usr/bin/sh\n", 0)

        passed, message = check_agent_reachable('sh -c "agent {prompt}"')

        self.assertTrue(passed)
        # Should extract 'sh' as the command
        mock_run_shell.assert_called_once_with("command -v sh", ignore_error=True)

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_whitespace_only_output(self, mock_run_shell):
        """Test check handles whitespace-only output."""
        mock_run_shell.return_value = (True, "   \n", 0)

        passed, message = check_agent_reachable("somecommand {prompt}")

        # Success but with whitespace output - should still pass if success=True
        # The check is: if success and output.strip()
        self.assertFalse(passed)
        self.assertIn("not found", message)

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_exception_handling(self, mock_run_shell):
        """Test check handles exceptions during parsing."""
        # This should not raise an exception from shlex.split
        # but let's test with a malformed template that might cause issues
        passed, message = check_agent_reachable("cmd'with'bad'quotes {prompt}")

        # Should handle gracefully and not crash
        self.assertIsInstance(passed, bool)
        self.assertIsInstance(message, str)

    @patch('src.preconditions.checks.run_shell')
    def test_check_agent_reachable_with_environment_vars(self, mock_run_shell):
        """Test check with environment variables in command."""
        mock_run_shell.return_value = (True, "/usr/bin/env\n", 0)

        passed, message = check_agent_reachable("env PYTHONPATH=/path python {prompt}")

        self.assertTrue(passed)
        # Should extract 'env' as the command to check
        mock_run_shell.assert_called_once_with("command -v env", ignore_error=True)


class TestPreconditionIntegration(unittest.TestCase):
    """Integration tests for precondition functions."""

    @patch('src.preconditions.checks.run_shell')
    def test_all_preconditions_pass(self, mock_run_shell):
        """Test that all preconditions can pass together."""
        def run_shell_side_effect(cmd, ignore_error=False):
            if "git status" in cmd:
                return (True, "", 0)
            elif "command -v" in cmd:
                return (True, "/usr/bin/echo\n", 0)
            elif "--collect-only" in cmd:
                return (True, "collected 5 tests\n", 0)
            else:
                return (True, "", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        git_passed, git_msg = check_git_clean()
        agent_passed, agent_msg = check_agent_reachable("echo {prompt}")
        tests_passed, tests_msg = check_tests_exist("pytest")

        self.assertTrue(git_passed)
        self.assertTrue(agent_passed)
        self.assertTrue(tests_passed)

    @patch('src.preconditions.checks.run_shell')
    def test_preconditions_fail_gracefully(self, mock_run_shell):
        """Test that precondition failures are graceful."""
        # All checks should return (False, message) on failure
        mock_run_shell.return_value = (False, "error", 1)

        git_passed, git_msg = check_git_clean()
        agent_passed, agent_msg = check_agent_reachable("badcmd {prompt}")
        tests_passed, tests_msg = check_tests_exist("pytest")

        # All should fail but not raise exceptions
        self.assertFalse(git_passed)
        self.assertFalse(agent_passed)
        self.assertFalse(tests_passed)

        # All should have informative messages
        self.assertIsInstance(git_msg, str)
        self.assertIsInstance(agent_msg, str)
        self.assertIsInstance(tests_msg, str)
        self.assertTrue(len(git_msg) > 0)
        self.assertTrue(len(agent_msg) > 0)
        self.assertTrue(len(tests_msg) > 0)


if __name__ == "__main__":
    unittest.main()

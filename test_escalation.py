#!/usr/bin/env python3
"""Unit tests for src/models/escalation.py module.

Tests the escalation protocol execution strategy.
"""

import unittest
from unittest.mock import patch, MagicMock, call
from src.models.escalation import EscalationExecutor, DEFAULT_MODELS, DEFAULT_AGENT_TIMEOUT


class TestEscalationExecutorInitialization(unittest.TestCase):
    """Tests for EscalationExecutor initialization."""

    def test_escalation_executor_initialization(self):
        """Test that executor initializes with correct parameters."""
        executor = EscalationExecutor(
            agent_cmd_template="claude {prompt}",
            verify_cmd="pytest",
            models=["model1", "model2"],
            agent_timeout=600
        )

        self.assertEqual(executor.agent_cmd_template, "claude {prompt}")
        self.assertEqual(executor.verify_cmd, "pytest")
        self.assertEqual(executor.models, ["model1", "model2"])
        self.assertEqual(executor.agent_timeout, 600)

    def test_escalation_executor_default_models(self):
        """Test that executor uses default models when none provided."""
        executor = EscalationExecutor(
            agent_cmd_template="agent {prompt}",
            verify_cmd="true"
        )

        self.assertEqual(executor.models, DEFAULT_MODELS)

    def test_escalation_executor_default_timeout(self):
        """Test that executor uses default timeout when none provided."""
        executor = EscalationExecutor(
            agent_cmd_template="agent {prompt}",
            verify_cmd="true"
        )

        self.assertEqual(executor.agent_timeout, DEFAULT_AGENT_TIMEOUT)


class TestEscalationSuccess(unittest.TestCase):
    """Tests for successful escalation scenarios."""

    @patch('src.models.escalation.run_shell')
    @patch('src.models.escalation.has_changes')
    @patch('src.models.escalation.get_diff_summary')
    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    @patch('src.models.escalation.parse_context_files')
    @patch('src.models.escalation.get_default_context_files')
    @patch('src.models.escalation.build_static_context')
    def test_escalation_success_on_first_try(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_tests,
        mock_check_agent,
        mock_check_git,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test successful execution on first model attempt."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_check_tests.return_value = (True, "Collected 5 tests")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("", 0)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "1 file changed"

        # Mock run_shell calls
        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            elif "pytest" in cmd or "verify" in cmd:
                return (True, "All tests passed", 0)
            else:  # Agent command
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = EscalationExecutor("agent {prompt}", "pytest", models=["model1"])
        result = executor.execute("Fix the bug")

        self.assertTrue(result)
        # Verify agent was called only once (first model succeeded)
        agent_calls = [c for c in mock_run_shell.call_args_list if "agent" in str(c)]
        self.assertEqual(len(agent_calls), 1)

    @patch('src.models.escalation.run_shell')
    @patch('src.models.escalation.has_changes')
    @patch('src.models.escalation.get_diff_summary')
    @patch('src.models.escalation.get_diff_content')
    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    @patch('src.models.escalation.parse_context_files')
    @patch('src.models.escalation.get_default_context_files')
    @patch('src.models.escalation.build_static_context')
    def test_escalation_to_next_model(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_tests,
        mock_check_agent,
        mock_check_git,
        mock_diff_content,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test escalation to next model after first fails."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_check_tests.return_value = (True, "Collected 5 tests")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("", 0)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "1 file changed"
        mock_diff_content.return_value = "diff content"

        call_count = [0]

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git reset" in cmd or "git clean" in cmd:
                return (True, "", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            elif "pytest" in cmd or cmd == "verify":
                # First verify fails, second succeeds
                call_count[0] += 1
                if call_count[0] == 1:
                    return (False, "Test failed", 1)
                else:
                    return (True, "All tests passed", 0)
            else:  # Agent command
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = EscalationExecutor("agent {prompt}", "verify", models=["model1", "model2"])
        result = executor.execute("Fix the bug")

        self.assertTrue(result)
        # Verify both models were tried
        agent_calls = [c for c in mock_run_shell.call_args_list if "agent" in str(c)]
        self.assertEqual(len(agent_calls), 2)


class TestEscalationFailure(unittest.TestCase):
    """Tests for escalation failure scenarios."""

    @patch('src.models.escalation.run_shell')
    @patch('src.models.escalation.has_changes')
    @patch('src.models.escalation.get_diff_summary')
    @patch('src.models.escalation.get_diff_content')
    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    @patch('src.models.escalation.parse_context_files')
    @patch('src.models.escalation.get_default_context_files')
    @patch('src.models.escalation.build_static_context')
    def test_escalation_all_models_fail(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_tests,
        mock_check_agent,
        mock_check_git,
        mock_diff_content,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test that execution fails when all models fail."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_check_tests.return_value = (True, "Collected 5 tests")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("", 0)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "1 file changed"
        mock_diff_content.return_value = "diff content"

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git reset" in cmd or "git clean" in cmd:
                return (True, "", 0)
            elif "pytest" in cmd or cmd == "verify":
                # All verifications fail
                return (False, "Test failed", 1)
            else:  # Agent command
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = EscalationExecutor(
            "agent {prompt}",
            "verify",
            models=["model1", "model2", "model3"]
        )
        result = executor.execute("Fix the bug")

        self.assertFalse(result)
        # Verify all 3 models were tried
        agent_calls = [c for c in mock_run_shell.call_args_list if "agent" in str(c)]
        self.assertEqual(len(agent_calls), 3)
        # Verify stash pop was called (rollback)
        stash_pop_calls = [c for c in mock_run_shell.call_args_list if "git stash pop" in str(c)]
        self.assertEqual(len(stash_pop_calls), 1)

    @patch('src.models.escalation.run_shell')
    @patch('src.models.escalation.has_changes')
    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    @patch('src.models.escalation.parse_context_files')
    @patch('src.models.escalation.get_default_context_files')
    @patch('src.models.escalation.build_static_context')
    def test_escalation_agent_no_changes(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_tests,
        mock_check_agent,
        mock_check_git,
        mock_has_changes,
        mock_run_shell
    ):
        """Test that agent producing no changes triggers retry."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_check_tests.return_value = (True, "Collected 5 tests")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("", 0)
        mock_has_changes.return_value = False  # No changes

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git reset" in cmd or "git clean" in cmd:
                return (True, "", 0)
            else:  # Agent command
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = EscalationExecutor("agent {prompt}", "verify", models=["model1", "model2"])
        result = executor.execute("Fix the bug")

        self.assertFalse(result)
        # Verify all models were tried (no changes, so kept retrying)
        agent_calls = [c for c in mock_run_shell.call_args_list if "agent" in str(c)]
        self.assertEqual(len(agent_calls), 2)


class TestPreconditionFailures(unittest.TestCase):
    """Tests for precondition check failures."""

    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    def test_precondition_git_dirty_fails(
        self,
        mock_check_tests,
        mock_check_agent,
        mock_check_git
    ):
        """Test that execution fails when git working tree is dirty."""
        mock_check_git.return_value = (False, "Working tree has uncommitted changes")

        executor = EscalationExecutor("agent {prompt}", "pytest")
        result = executor.execute("Fix the bug")

        self.assertFalse(result)
        # Other preconditions should not be checked
        mock_check_agent.assert_not_called()
        mock_check_tests.assert_not_called()

    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    def test_precondition_agent_not_reachable_fails(
        self,
        mock_check_tests,
        mock_check_agent,
        mock_check_git
    ):
        """Test that execution fails when agent is not reachable."""
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (False, "Agent command not found")

        executor = EscalationExecutor("nonexistent {prompt}", "pytest")
        result = executor.execute("Fix the bug")

        self.assertFalse(result)
        # Tests check should not run after agent check fails
        mock_check_tests.assert_not_called()

    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    def test_precondition_no_tests_fails(
        self,
        mock_check_tests,
        mock_check_agent,
        mock_check_git
    ):
        """Test that execution fails when no tests exist."""
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_check_tests.return_value = (False, "No tests collected")

        executor = EscalationExecutor("agent {prompt}", "pytest")
        result = executor.execute("Fix the bug")

        self.assertFalse(result)

    @patch('src.models.escalation.run_shell')
    @patch('src.models.escalation.has_changes')
    @patch('src.models.escalation.get_diff_summary')
    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    @patch('src.models.escalation.parse_context_files')
    @patch('src.models.escalation.get_default_context_files')
    @patch('src.models.escalation.build_static_context')
    def test_commit_failure_after_verification(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_tests,
        mock_check_agent,
        mock_check_git,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test handling when commit fails after verification passes."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_check_tests.return_value = (True, "Collected 5 tests")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("", 0)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "1 file changed"

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git add . && git commit" in cmd:
                return (False, "Commit failed", 1)  # Commit fails
            elif "pytest" in cmd or cmd == "verify":
                return (True, "All tests passed", 0)
            else:  # Agent command
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = EscalationExecutor("agent {prompt}", "verify", models=["model1"])
        result = executor.execute("Fix the bug")

        self.assertFalse(result)

    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    def test_precondition_exception_handling(
        self,
        mock_check_tests,
        mock_check_agent,
        mock_check_git
    ):
        """Test that execution fails safely when precondition check raises exception."""
        mock_check_git.side_effect = RuntimeError("Unexpected error in git check")

        executor = EscalationExecutor("agent {prompt}", "pytest")
        result = executor.execute("Fix the bug")

        self.assertFalse(result)
        # Subsequent checks should not run after exception
        mock_check_agent.assert_not_called()
        mock_check_tests.assert_not_called()

    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    def test_precondition_invalid_return_type(
        self,
        mock_check_tests,
        mock_check_agent,
        mock_check_git
    ):
        """Test that execution fails when precondition check returns invalid type."""
        # Return a string instead of (bool, str) tuple
        mock_check_git.return_value = "Not a tuple"

        executor = EscalationExecutor("agent {prompt}", "pytest")
        result = executor.execute("Fix the bug")

        self.assertFalse(result)
        # Subsequent checks should not run after type validation failure
        mock_check_agent.assert_not_called()
        mock_check_tests.assert_not_called()

    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    def test_precondition_wrong_tuple_length(
        self,
        mock_check_tests,
        mock_check_agent,
        mock_check_git
    ):
        """Test that execution fails when precondition check returns wrong tuple length."""
        # Return tuple with wrong number of elements
        mock_check_git.return_value = (True,)  # Missing message

        executor = EscalationExecutor("agent {prompt}", "pytest")
        result = executor.execute("Fix the bug")

        self.assertFalse(result)
        # Subsequent checks should not run
        mock_check_agent.assert_not_called()
        mock_check_tests.assert_not_called()


class TestContextHandling(unittest.TestCase):
    """Tests for context file handling in escalation."""

    @patch('src.models.escalation.run_shell')
    @patch('src.models.escalation.has_changes')
    @patch('src.models.escalation.get_diff_summary')
    @patch('src.models.escalation.check_git_clean')
    @patch('src.models.escalation.check_agent_reachable')
    @patch('src.models.escalation.check_tests_exist')
    @patch('src.models.escalation.parse_context_files')
    @patch('src.models.escalation.get_default_context_files')
    @patch('src.models.escalation.build_static_context')
    def test_context_files_from_task(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_tests,
        mock_check_agent,
        mock_check_git,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test that context files are parsed from task."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_check_tests.return_value = (True, "Collected 5 tests")
        mock_parse.return_value = ["file1.py", "file2.py"]
        mock_build_context.return_value = ("context content", 1000)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "1 file changed"

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            elif "pytest" in cmd:
                return (True, "All tests passed", 0)
            else:  # Agent command
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = EscalationExecutor("agent {prompt}", "pytest", models=["model1"])
        task = 'Fix bug context_files: ["file1.py", "file2.py"]'
        result = executor.execute(task)

        self.assertTrue(result)
        # Verify context was built with parsed files
        mock_build_context.assert_called_once_with(["file1.py", "file2.py"])


if __name__ == "__main__":
    unittest.main()

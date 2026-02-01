#!/usr/bin/env python3
"""Unit tests for src/models/two_phase.py module.

Tests the two-phase (architect/intern) execution strategy.
"""

import unittest
from unittest.mock import patch, MagicMock
from src.models.two_phase import TwoPhaseExecutor, DEFAULT_AGENT_TIMEOUT


class TestTwoPhaseExecutorInitialization(unittest.TestCase):
    """Tests for TwoPhaseExecutor initialization."""

    def test_two_phase_executor_initialization(self):
        """Test that executor initializes with correct parameters."""
        executor = TwoPhaseExecutor(
            agent_cmd_template="claude {prompt}",
            verify_cmd="pytest",
            test_model="sonnet",
            impl_model="haiku",
            agent_timeout=600
        )

        self.assertEqual(executor.agent_cmd_template, "claude {prompt}")
        self.assertEqual(executor.verify_cmd, "pytest")
        self.assertEqual(executor.test_model, "sonnet")
        self.assertEqual(executor.impl_model, "haiku")
        self.assertEqual(executor.agent_timeout, 600)

    def test_two_phase_executor_default_timeout(self):
        """Test that executor uses default timeout when none provided."""
        executor = TwoPhaseExecutor(
            agent_cmd_template="agent {prompt}",
            verify_cmd="pytest",
            test_model="sonnet",
            impl_model="haiku"
        )

        self.assertEqual(executor.agent_timeout, DEFAULT_AGENT_TIMEOUT)


class TestTestGenerationPhase(unittest.TestCase):
    """Tests for test generation phase."""

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.get_diff_summary')
    @patch('src.models.two_phase.build_static_context')
    def test_test_generation_success(
        self,
        mock_build_context,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test successful test generation."""
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "test_example.py | 10 ++++++++"

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            else:  # Agent command
                return (True, "Test generated", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.run_test_generation_phase("Create add function", [])

        self.assertTrue(result)
        # Verify commit was attempted
        commit_calls = [c for c in mock_run_shell.call_args_list if "git add . && git commit" in str(c)]
        self.assertEqual(len(commit_calls), 1)

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.build_static_context')
    def test_test_generation_failure_no_changes(
        self,
        mock_build_context,
        mock_has_changes,
        mock_run_shell
    ):
        """Test test generation fails when no changes produced."""
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = False  # No changes

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.run_test_generation_phase("Create add function", [])

        self.assertFalse(result)

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.get_diff_summary')
    @patch('src.models.two_phase.build_static_context')
    def test_test_generation_failure_commit_fails(
        self,
        mock_build_context,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test test generation fails when commit fails."""
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "test_example.py | 10 ++++++++"

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git add . && git commit" in cmd:
                return (False, "Commit failed", 1)  # Commit fails
            else:  # Agent command
                return (True, "Test generated", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.run_test_generation_phase("Create add function", [])

        self.assertFalse(result)


class TestImplementationPhase(unittest.TestCase):
    """Tests for implementation phase."""

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.get_diff_summary')
    @patch('src.models.two_phase.build_static_context')
    def test_implementation_success(
        self,
        mock_build_context,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test successful implementation."""
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "calculator.py | 5 +++++"

        call_count = [0]

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "pytest" in cmd:
                call_count[0] += 1
                if call_count[0] == 1:
                    return (False, "Test failed initially", 1)
                else:
                    return (True, "All tests passed", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            else:  # Agent command
                return (True, "Implementation done", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.run_implementation_phase("Implement add function", [])

        self.assertTrue(result)
        # Verify tests were run twice (before and after implementation)
        test_calls = [c for c in mock_run_shell.call_args_list if "pytest" in str(c)]
        self.assertEqual(len(test_calls), 2)

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.build_static_context')
    def test_implementation_tests_already_pass(
        self,
        mock_build_context,
        mock_run_shell
    ):
        """Test implementation phase when tests already pass."""
        mock_build_context.return_value = ("context", 100)

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "pytest" in cmd:
                return (True, "All tests passed", 0)  # Already passing
            else:
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.run_implementation_phase("Implement add function", [])

        self.assertTrue(result)

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.build_static_context')
    def test_implementation_failure_no_changes(
        self,
        mock_build_context,
        mock_has_changes,
        mock_run_shell
    ):
        """Test implementation fails when no changes produced."""
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = False  # No changes

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "pytest" in cmd:
                return (False, "Test failed", 1)
            else:
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.run_implementation_phase("Implement add function", [])

        self.assertFalse(result)

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.get_diff_summary')
    @patch('src.models.two_phase.build_static_context')
    def test_implementation_failure_tests_still_fail(
        self,
        mock_build_context,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test implementation fails when tests still fail after implementation."""
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "calculator.py | 5 +++++"

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "pytest" in cmd:
                return (False, "Tests still failing", 1)  # Always fail
            else:
                return (True, "Implementation done", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.run_implementation_phase("Implement add function", [])

        self.assertFalse(result)


class TestFullTwoPhaseWorkflow(unittest.TestCase):
    """Tests for complete two-phase execution workflow."""

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.get_diff_summary')
    @patch('src.models.two_phase.check_git_clean')
    @patch('src.models.two_phase.check_agent_reachable')
    @patch('src.models.two_phase.parse_context_files')
    @patch('src.models.two_phase.get_default_context_files')
    @patch('src.models.two_phase.build_static_context')
    def test_full_two_phase_workflow_success(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_agent,
        mock_check_git,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test complete two-phase workflow from start to finish."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "1 file changed"

        test_call_count = [0]

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            elif cmd.strip().startswith("pytest") or cmd.strip() == "pytest":
                test_call_count[0] += 1
                if test_call_count[0] == 1:
                    return (False, "Test failed initially", 1)
                else:
                    return (True, "All tests passed", 0)
            else:  # Agent commands
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.execute("Create add function")

        self.assertTrue(result)
        # Verify two commits were made (test + implementation)
        commit_calls = [c for c in mock_run_shell.call_args_list if "git add . && git commit" in str(c)]
        self.assertEqual(len(commit_calls), 2)

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.check_git_clean')
    @patch('src.models.two_phase.check_agent_reachable')
    @patch('src.models.two_phase.parse_context_files')
    @patch('src.models.two_phase.get_default_context_files')
    @patch('src.models.two_phase.build_static_context')
    def test_full_two_phase_workflow_test_gen_fails(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_agent,
        mock_check_git,
        mock_has_changes,
        mock_run_shell
    ):
        """Test workflow fails and rolls back when test generation fails."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = False  # No changes in test generation

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd or "git reset" in cmd:
                return (True, "", 0)
            else:
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.execute("Create add function")

        self.assertFalse(result)
        # Verify rollback occurred
        reset_calls = [c for c in mock_run_shell.call_args_list if "git reset --hard HEAD" in str(c)]
        self.assertEqual(len(reset_calls), 1)

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.get_diff_summary')
    @patch('src.models.two_phase.check_git_clean')
    @patch('src.models.two_phase.check_agent_reachable')
    @patch('src.models.two_phase.parse_context_files')
    @patch('src.models.two_phase.get_default_context_files')
    @patch('src.models.two_phase.build_static_context')
    def test_full_two_phase_workflow_impl_fails(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_agent,
        mock_check_git,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test workflow fails and rolls back when implementation fails."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("context", 100)
        mock_diff_summary.return_value = "1 file changed"

        call_count = [0]

        def has_changes_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return True  # Test generation has changes
            else:
                return False  # Implementation has no changes

        mock_has_changes.side_effect = has_changes_side_effect

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd or "git reset" in cmd or "git clean" in cmd:
                return (True, "", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            elif "pytest" in cmd:
                return (False, "Test failed", 1)
            else:
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.execute("Create add function")

        self.assertFalse(result)
        # Verify rollback occurred (git reset --hard HEAD~1 to undo test commit)
        reset_calls = [c for c in mock_run_shell.call_args_list if "git reset --hard HEAD~1" in str(c)]
        self.assertEqual(len(reset_calls), 1)

    @patch('src.models.two_phase.check_git_clean')
    @patch('src.models.two_phase.check_agent_reachable')
    def test_full_two_phase_workflow_precondition_fails(
        self,
        mock_check_agent,
        mock_check_git
    ):
        """Test workflow fails early when preconditions not met."""
        mock_check_git.return_value = (False, "Working tree has uncommitted changes")

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.execute("Create add function")

        self.assertFalse(result)
        # Agent reachability should not be checked after git clean fails
        mock_check_agent.assert_not_called()

    @patch('src.models.two_phase.check_git_clean')
    @patch('src.models.two_phase.check_agent_reachable')
    def test_precondition_exception_handling(
        self,
        mock_check_agent,
        mock_check_git
    ):
        """Test that execution fails safely when precondition check raises exception."""
        mock_check_git.side_effect = RuntimeError("Unexpected error in git check")

        executor = TwoPhaseExecutor(
            agent_cmd_template="claude {prompt}",
            verify_cmd="pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.execute("Create add function")

        self.assertFalse(result)
        # Subsequent checks should not run after exception
        mock_check_agent.assert_not_called()

    @patch('src.models.two_phase.check_git_clean')
    @patch('src.models.two_phase.check_agent_reachable')
    def test_precondition_invalid_return_type(
        self,
        mock_check_agent,
        mock_check_git
    ):
        """Test that execution fails when precondition check returns invalid type."""
        # Return a list instead of (bool, str) tuple
        mock_check_git.return_value = ["Not", "a", "tuple"]

        executor = TwoPhaseExecutor(
            agent_cmd_template="claude {prompt}",
            verify_cmd="pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        result = executor.execute("Create add function")

        self.assertFalse(result)
        # Subsequent checks should not run
        mock_check_agent.assert_not_called()


class TestContextHandling(unittest.TestCase):
    """Tests for context file handling in two-phase mode."""

    @patch('src.models.two_phase.run_shell')
    @patch('src.models.two_phase.has_changes')
    @patch('src.models.two_phase.get_diff_summary')
    @patch('src.models.two_phase.check_git_clean')
    @patch('src.models.two_phase.check_agent_reachable')
    @patch('src.models.two_phase.parse_context_files')
    @patch('src.models.two_phase.get_default_context_files')
    @patch('src.models.two_phase.build_static_context')
    def test_context_files_parsed_and_used(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_agent,
        mock_check_git,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test that context files are parsed and used in both phases."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_parse.return_value = ["file1.py", "file2.py"]
        mock_build_context.return_value = ("context content", 1000)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "1 file changed"

        test_call_count = [0]

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            elif cmd.strip().startswith("pytest") or cmd.strip() == "pytest":
                test_call_count[0] += 1
                if test_call_count[0] == 1:
                    return (False, "Test failed", 1)
                else:
                    return (True, "Tests passed", 0)
            else:
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = TwoPhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku"
        )
        task = 'Create add function context_files: ["file1.py", "file2.py"]'
        result = executor.execute(task)

        self.assertTrue(result)
        # Verify context was built twice (once for each phase)
        self.assertEqual(mock_build_context.call_count, 2)
        mock_build_context.assert_called_with(["file1.py", "file2.py"])


if __name__ == "__main__":
    unittest.main()

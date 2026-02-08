#!/usr/bin/env python3
"""Unit tests for src/models/three_phase.py module.

Tests the three-phase (architect/intern/adversary) execution strategy.
"""

import unittest
from unittest.mock import patch
from src.models.three_phase import ThreePhaseExecutor, DEFAULT_AGENT_TIMEOUT, DEFAULT_EXECUTION_TIMEOUT


class TestThreePhaseExecutorInitialization(unittest.TestCase):
    """Tests for ThreePhaseExecutor initialization."""

    def test_three_phase_executor_initialization(self):
        """Test that executor initializes with correct parameters."""
        executor = ThreePhaseExecutor(
            agent_cmd_template="claude {prompt}",
            verify_cmd="pytest",
            test_model="sonnet",
            impl_model="haiku",
            adversary_model="sonnet",
            agent_timeout=600
        )

        self.assertEqual(executor.agent_cmd_template, "claude {prompt}")
        self.assertEqual(executor.verify_cmd, "pytest")
        self.assertEqual(executor.test_model, "sonnet")
        self.assertEqual(executor.impl_model, "haiku")
        self.assertEqual(executor.adversary_model, "sonnet")
        self.assertEqual(executor.agent_timeout, 600)

    def test_three_phase_executor_default_timeout(self):
        """Test that executor uses default timeout when none provided."""
        executor = ThreePhaseExecutor(
            agent_cmd_template="agent {prompt}",
            verify_cmd="pytest",
            test_model="sonnet",
            impl_model="haiku",
            adversary_model="sonnet"
        )

        self.assertEqual(executor.agent_timeout, DEFAULT_AGENT_TIMEOUT)


class TestAdversarialReviewPhase(unittest.TestCase):
    """Tests for adversarial review phase."""

    @patch('src.models.three_phase.run_shell')
    @patch('src.models.three_phase.has_changes')
    @patch('src.models.three_phase.get_diff_summary')
    @patch('src.models.three_phase.build_static_context')
    def test_adversarial_review_adds_hardening_tests(
        self,
        mock_build_context,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell
    ):
        """Test successful adversarial review that adds hardening tests."""
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "test_example.py | 5 +++++"

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "find . -type f -name 'test_*.py'" in cmd:
                return (True, "./test_example.py\n", 0)
            elif "cat " in cmd and "test_example.py" in cmd:
                return (True, "def test_basic(): assert True", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed hardening tests", 0)
            else:  # Agent command
                return (True, "Hardening tests added", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = ThreePhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku",
            adversary_model="sonnet"
        )
        result = executor.run_adversarial_review_phase("Create add function", [])

        self.assertTrue(result)
        # Verify commit was attempted
        commit_calls = [c for c in mock_run_shell.call_args_list if "git add . && git commit" in str(c)]
        self.assertEqual(len(commit_calls), 1)

    @patch('src.models.three_phase.run_shell')
    @patch('src.models.three_phase.has_changes')
    @patch('src.models.three_phase.build_static_context')
    def test_adversarial_review_no_changes_is_ok(
        self,
        mock_build_context,
        mock_has_changes,
        mock_run_shell
    ):
        """Test that adversarial review succeeds even if no hardening tests added."""
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = False  # No hardening tests needed

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "find . -type f -name 'test_*.py'" in cmd:
                return (True, "./test_example.py\n", 0)
            elif "cat " in cmd:
                return (True, "def test_basic(): assert True", 0)
            else:
                return (True, "No changes needed", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = ThreePhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku",
            adversary_model="sonnet"
        )
        result = executor.run_adversarial_review_phase("Create add function", [])

        self.assertTrue(result)  # No changes is not a failure

    @patch('src.models.three_phase.run_shell')
    @patch('src.models.three_phase.build_static_context')
    def test_adversarial_review_no_test_files_fails(
        self,
        mock_build_context,
        mock_run_shell
    ):
        """Test that adversarial review fails if no test files found."""
        mock_build_context.return_value = ("context", 100)

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "find . -type f -name 'test_*.py'" in cmd:
                return (False, "", 1)  # No test files found
            else:
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = ThreePhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku",
            adversary_model="sonnet"
        )
        result = executor.run_adversarial_review_phase("Create add function", [])

        self.assertFalse(result)


class TestFullThreePhaseWorkflow(unittest.TestCase):
    """Tests for complete three-phase execution workflow."""

    @patch('src.models.three_phase.run_shell')
    @patch('src.models.three_phase.run_shell_with_retry')
    @patch('src.models.three_phase.has_changes')
    @patch('src.models.three_phase.get_diff_summary')
    @patch('src.models.three_phase.check_git_clean')
    @patch('src.models.three_phase.check_agent_reachable')
    @patch('src.models.three_phase.parse_context_files')
    @patch('src.models.three_phase.get_default_context_files')
    @patch('src.models.three_phase.build_static_context')
    def test_full_three_phase_workflow_success_with_hardening(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_agent,
        mock_check_git,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell_retry,
        mock_run_shell
    ):
        """Test complete three-phase workflow with hardening tests."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("context", 100)
        mock_has_changes.return_value = True
        mock_diff_summary.return_value = "1 file changed"
        mock_run_shell_retry.return_value = (True, "Agent output", 0)

        test_call_count = [0]

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            elif "find . -type f -name 'test_*.py'" in cmd:
                return (True, "./test_example.py\n", 0)
            elif "cat " in cmd and "test_example.py" in cmd:
                return (True, "def test_basic(): assert True", 0)
            elif cmd.strip().startswith("pytest") or cmd.strip() == "pytest":
                test_call_count[0] += 1
                # Call 1: Phase 2 initial check (fail)
                # Call 2: Phase 2 verify (pass)
                # Call 3: Pre-Phase 4 hardening check (fail)
                # Call 4: Phase 4 initial check (fail)
                # Call 5: Phase 4 verify (pass)
                if test_call_count[0] in [1, 3, 4]:
                    return (False, "Test failed", 1)
                else:
                    return (True, "Tests passed", 0)
            else:
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = ThreePhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku",
            adversary_model="sonnet"
        )
        result = executor.execute("Create add function")

        self.assertTrue(result)
        # Verify four commits: test gen, initial impl, hardening tests, hardening impl
        commit_calls = [c for c in mock_run_shell.call_args_list if "git add . && git commit" in str(c)]
        self.assertEqual(len(commit_calls), 4)

    @patch('src.models.three_phase.run_shell')
    @patch('src.models.three_phase.run_shell_with_retry')
    @patch('src.models.three_phase.has_changes')
    @patch('src.models.three_phase.get_diff_summary')
    @patch('src.models.three_phase.check_git_clean')
    @patch('src.models.three_phase.check_agent_reachable')
    @patch('src.models.three_phase.parse_context_files')
    @patch('src.models.three_phase.get_default_context_files')
    @patch('src.models.three_phase.build_static_context')
    def test_full_three_phase_workflow_success_without_hardening(
        self,
        mock_build_context,
        mock_get_default,
        mock_parse,
        mock_check_agent,
        mock_check_git,
        mock_diff_summary,
        mock_has_changes,
        mock_run_shell_retry,
        mock_run_shell
    ):
        """Test three-phase workflow when adversary adds no hardening tests."""
        # Setup mocks
        mock_check_git.return_value = (True, "Working tree is clean")
        mock_check_agent.return_value = (True, "Agent is reachable")
        mock_parse.return_value = None
        mock_get_default.return_value = []
        mock_build_context.return_value = ("context", 100)
        mock_run_shell_retry.return_value = (True, "Agent output", 0)

        has_changes_count = [0]

        def has_changes_side_effect():
            has_changes_count[0] += 1
            # First two calls (test gen, impl) have changes, adversary has no changes
            return has_changes_count[0] <= 2

        mock_has_changes.side_effect = has_changes_side_effect
        mock_diff_summary.return_value = "1 file changed"

        test_call_count = [0]

        def run_shell_side_effect(cmd, ignore_error=False, timeout=None):
            if "git stash" in cmd:
                return (True, "", 0)
            elif "git add . && git commit" in cmd:
                return (True, "Committed", 0)
            elif "find . -type f -name 'test_*.py'" in cmd:
                return (True, "./test_example.py\n", 0)
            elif "cat " in cmd and "test_example.py" in cmd:
                return (True, "def test_basic(): assert True", 0)
            elif cmd.strip().startswith("pytest") or cmd.strip() == "pytest":
                test_call_count[0] += 1
                if test_call_count[0] == 1:
                    return (False, "Test failed", 1)
                else:
                    return (True, "Tests passed", 0)
            else:
                return (True, "Agent output", 0)

        mock_run_shell.side_effect = run_shell_side_effect

        executor = ThreePhaseExecutor(
            "agent {prompt}",
            "pytest",
            test_model="sonnet",
            impl_model="haiku",
            adversary_model="sonnet"
        )
        result = executor.execute("Create add function")

        self.assertTrue(result)  # Still succeeds even without hardening
        # Only two commits: test gen, initial impl (no hardening commits)
        commit_calls = [c for c in mock_run_shell.call_args_list if "git add . && git commit" in str(c)]
        self.assertEqual(len(commit_calls), 2)


if __name__ == "__main__":
    unittest.main()

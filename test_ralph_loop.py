#!/usr/bin/env python3
"""Unit tests for ralph_loop.py module."""

import unittest
import tempfile
import json
from pathlib import Path
from ralph_loop import SpecTracker, RalphLoop


class TestSpecTracker(unittest.TestCase):
    """Tests for SpecTracker class."""

    def setUp(self):
        """Create temporary spec file for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode='w', delete=False, suffix='.json'
        )
        self.temp_file.close()
        self.spec_file = self.temp_file.name

    def tearDown(self):
        """Clean up temporary file."""
        Path(self.spec_file).unlink(missing_ok=True)

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        tracker = SpecTracker(spec_file=self.spec_file)
        self.assertEqual(len(tracker.items), 0)

    def test_add_item(self):
        """Test adding spec items."""
        tracker = SpecTracker(spec_file=self.spec_file)

        tracker.add_item("Implement login", check_cmd="pytest tests/test_login.py")
        tracker.add_item("Add validation")

        self.assertEqual(len(tracker.items), 2)
        self.assertEqual(tracker.items[0]['description'], "Implement login")
        self.assertEqual(tracker.items[0]['check_cmd'], "pytest tests/test_login.py")
        self.assertFalse(tracker.items[0]['completed'])

    def test_persistence(self):
        """Test saving and loading spec items."""
        tracker1 = SpecTracker(spec_file=self.spec_file)
        tracker1.add_item("Task 1")
        tracker1.add_item("Task 2")

        # Create new tracker with same file - should load items
        tracker2 = SpecTracker(spec_file=self.spec_file)
        self.assertEqual(len(tracker2.items), 2)
        self.assertEqual(tracker2.items[0]['description'], "Task 1")

    def test_get_status(self):
        """Test status string generation."""
        tracker = SpecTracker(spec_file=self.spec_file)
        tracker.add_item("Task 1")
        tracker.add_item("Task 2")

        status = tracker.get_status()
        self.assertIn("0/2 items complete", status)
        self.assertIn("Task 1", status)
        self.assertIn("Task 2", status)

        # Mark one complete
        tracker.items[0]['completed'] = True
        tracker._save()

        status = tracker.get_status()
        self.assertIn("1/2 items complete", status)

    def test_check_all_with_passing_command(self):
        """Test check_all with a passing verification command."""
        tracker = SpecTracker(spec_file=self.spec_file)
        tracker.add_item("Always passes", check_cmd="true")

        all_complete, failed = tracker.check_all(default_check="pytest")

        self.assertTrue(all_complete)
        self.assertEqual(len(failed), 0)
        self.assertTrue(tracker.items[0]['completed'])

    def test_check_all_with_failing_command(self):
        """Test check_all with a failing verification command."""
        tracker = SpecTracker(spec_file=self.spec_file)
        tracker.add_item("Always fails", check_cmd="false")

        all_complete, failed = tracker.check_all(default_check="pytest")

        self.assertFalse(all_complete)
        self.assertEqual(len(failed), 1)
        self.assertIn("Always fails", failed)
        self.assertFalse(tracker.items[0]['completed'])

    def test_check_all_mixed_results(self):
        """Test check_all with mix of passing and failing items."""
        tracker = SpecTracker(spec_file=self.spec_file)
        tracker.add_item("Passes", check_cmd="true")
        tracker.add_item("Fails", check_cmd="false")

        all_complete, failed = tracker.check_all(default_check="pytest")

        self.assertFalse(all_complete)
        self.assertEqual(len(failed), 1)
        self.assertIn("Fails", failed)
        self.assertTrue(tracker.items[0]['completed'])
        self.assertFalse(tracker.items[1]['completed'])


class TestRalphLoop(unittest.TestCase):
    """Tests for RalphLoop class."""

    def test_initialization(self):
        """Test RalphLoop initialization."""
        loop = RalphLoop(
            task_description="Test task",
            max_iterations=3,
            max_cost=0.50
        )

        self.assertEqual(loop.task_description, "Test task")
        self.assertEqual(loop.max_iterations, 3)
        self.assertEqual(loop.max_cost, 0.50)
        self.assertEqual(loop.iteration, 0)

    def test_build_initial_prompt(self):
        """Test initial prompt generation."""
        loop = RalphLoop(task_description="Implement feature X")

        prompt = loop._build_initial_prompt()

        self.assertIn("Implement feature X", prompt)
        self.assertIn("iteration 1", prompt.lower())
        self.assertIn("Ralph Loop", prompt)

    def test_build_retry_prompt(self):
        """Test retry prompt generation."""
        loop = RalphLoop(task_description="Fix bug Y")
        loop.iteration = 2

        failed_items = ["Tests still failing", "Coverage too low"]
        prompt = loop._build_retry_prompt(failed_items)

        self.assertIn("Fix bug Y", prompt)
        self.assertIn("RETRY", prompt)
        self.assertIn("2/", prompt)
        self.assertIn("Tests still failing", prompt)
        self.assertIn("Coverage too low", prompt)

    def test_get_git_diff(self):
        """Test git diff retrieval."""
        loop = RalphLoop(task_description="Test")

        # Should not crash even if git diff fails
        diff = loop._get_git_diff()
        self.assertIsInstance(diff, str)

    def test_fallback_agents_initialization(self):
        """Test initialization with fallback agents."""
        loop = RalphLoop(
            task_description="Test",
            agent_cmd="claude {prompt}",
            fallback_agents=["gh copilot suggest {prompt}", "aider {prompt}"]
        )

        self.assertEqual(loop.agent_cmd, "claude {prompt}")
        self.assertEqual(len(loop.fallback_agents), 2)
        self.assertEqual(loop.fallback_agents[0], "gh copilot suggest {prompt}")
        self.assertEqual(loop.fallback_agents[1], "aider {prompt}")

    def test_no_fallback_agents(self):
        """Test initialization without fallback agents."""
        loop = RalphLoop(task_description="Test")

        self.assertEqual(loop.agent_cmd, "claude -p --dangerously-skip-permissions --model {model} {prompt}")
        self.assertEqual(loop.fallback_agents, [])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for src/models/cost_tracker.py module.

Tests cost tracking, budget enforcement, and token parsing functionality.
"""

import unittest
import tempfile
import json
from pathlib import Path
from src.models.cost_tracker import (
    AgentCostTracker,
    CostMetrics,
    BudgetExceededException,
    parse_claude_tokens,
    MODEL_PRICING,
)


class TestCostMetrics(unittest.TestCase):
    """Tests for CostMetrics dataclass."""

    def test_cost_metrics_creation(self):
        """Test creating a CostMetrics instance."""
        metrics = CostMetrics(
            timestamp="2025-01-01T12:00:00",
            model="claude-4.5-haiku",
            phase="test",
            attempt_num=1,
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost_usd=0.0065,
            duration_seconds=10.5,
            success=True,
            retry_count=0
        )

        self.assertEqual(metrics.model, "claude-4.5-haiku")
        self.assertEqual(metrics.input_tokens, 1000)
        self.assertEqual(metrics.output_tokens, 500)
        self.assertEqual(metrics.total_tokens, 1500)
        self.assertTrue(metrics.success)

    def test_cost_metrics_to_dict(self):
        """Test converting CostMetrics to dictionary."""
        metrics = CostMetrics(
            timestamp="2025-01-01T12:00:00",
            model="claude-4.5-sonnet",
            phase="implementation",
            attempt_num=1,
            input_tokens=2000,
            output_tokens=1000,
            total_tokens=3000,
            estimated_cost_usd=0.021,
            duration_seconds=15.0,
            success=True,
            retry_count=0
        )

        result = metrics.to_dict()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["model"], "claude-4.5-sonnet")
        self.assertEqual(result["total_tokens"], 3000)


class TestAgentCostTracker(unittest.TestCase):
    """Tests for AgentCostTracker class."""

    def setUp(self):
        """Create a temporary metrics file for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.metrics_path = self.temp_file.name

    def tearDown(self):
        """Clean up temporary file."""
        Path(self.metrics_path).unlink(missing_ok=True)

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        self.assertEqual(tracker.current_run_cost, 0.0)
        self.assertEqual(tracker.current_run_tokens, 0)
        self.assertEqual(len(tracker.history), 0)

    def test_tracker_with_budget_limits(self):
        """Test tracker initialization with budget limits."""
        tracker = AgentCostTracker(
            metrics_path=self.metrics_path,
            max_cost_per_run=1.0,
            max_tokens_per_run=100000
        )
        self.assertEqual(tracker.max_cost_per_run, 1.0)
        self.assertEqual(tracker.max_tokens_per_run, 100000)

    def test_calculate_cost_haiku(self):
        """Test cost calculation for Haiku model."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        cost = tracker.calculate_cost("claude-4.5-haiku", 1000, 500)

        # Expected: (1000/1M * $1) + (500/1M * $5) = 0.001 + 0.0025 = 0.0035
        self.assertAlmostEqual(cost, 0.0035, places=6)

    def test_calculate_cost_sonnet(self):
        """Test cost calculation for Sonnet model."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        cost = tracker.calculate_cost("claude-4.5-sonnet", 2000, 1000)

        # Expected: (2000/1M * $3) + (1000/1M * $15) = 0.006 + 0.015 = 0.021
        self.assertAlmostEqual(cost, 0.021, places=6)

    def test_calculate_cost_opus(self):
        """Test cost calculation for Opus model."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        cost = tracker.calculate_cost("claude-4.5-opus", 1000, 1000)

        # Expected: (1000/1M * $15) + (1000/1M * $75) = 0.015 + 0.075 = 0.09
        self.assertAlmostEqual(cost, 0.09, places=6)

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model defaults to Sonnet."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        cost = tracker.calculate_cost("unknown-model", 2000, 1000)

        # Should use Sonnet pricing as default
        expected_cost = (2000 / 1_000_000) * 3.0 + (1000 / 1_000_000) * 15.0
        self.assertAlmostEqual(cost, expected_cost, places=6)

    def test_record_execution(self):
        """Test recording an execution."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        tracker.reset_run_budget()

        metrics = tracker.record_execution(
            model="claude-4.5-haiku",
            phase="test",
            attempt_num=1,
            input_tokens=1000,
            output_tokens=500,
            duration_seconds=10.0,
            success=True,
            retry_count=0
        )

        self.assertIsInstance(metrics, CostMetrics)
        self.assertEqual(len(tracker.history), 1)
        self.assertGreater(tracker.current_run_cost, 0)
        self.assertEqual(tracker.current_run_tokens, 1500)

    def test_budget_exceeded_cost(self):
        """Test cost budget enforcement."""
        tracker = AgentCostTracker(
            metrics_path=self.metrics_path,
            max_cost_per_run=0.001  # Very low budget
        )
        tracker.reset_run_budget()

        with self.assertRaises(BudgetExceededException) as context:
            tracker.record_execution(
                model="claude-4.5-haiku",
                phase="test",
                attempt_num=1,
                input_tokens=10000,  # High token count to exceed budget
                output_tokens=5000,
                duration_seconds=10.0,
                success=True,
                retry_count=0
            )

        self.assertIn("Cost budget exceeded", str(context.exception))

    def test_budget_exceeded_tokens(self):
        """Test token budget enforcement."""
        tracker = AgentCostTracker(
            metrics_path=self.metrics_path,
            max_tokens_per_run=1000  # Low token budget
        )
        tracker.reset_run_budget()

        with self.assertRaises(BudgetExceededException) as context:
            tracker.record_execution(
                model="claude-4.5-haiku",
                phase="test",
                attempt_num=1,
                input_tokens=800,
                output_tokens=400,  # Total 1200 exceeds 1000
                duration_seconds=10.0,
                success=True,
                retry_count=0
            )

        self.assertIn("Token budget exceeded", str(context.exception))

    def test_reset_run_budget(self):
        """Test resetting run budget."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        tracker.current_run_cost = 1.0
        tracker.current_run_tokens = 10000

        tracker.reset_run_budget()

        self.assertEqual(tracker.current_run_cost, 0.0)
        self.assertEqual(tracker.current_run_tokens, 0)

    def test_get_run_summary_no_budget(self):
        """Test run summary without budget limits."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        tracker.reset_run_budget()

        tracker.record_execution(
            model="claude-4.5-haiku",
            phase="test",
            attempt_num=1,
            input_tokens=1000,
            output_tokens=500,
            duration_seconds=10.0,
            success=True,
            retry_count=0
        )

        summary = tracker.get_run_summary()

        self.assertIn("total_cost_usd", summary)
        self.assertIn("total_tokens", summary)
        self.assertEqual(summary["total_tokens"], 1500)
        self.assertGreater(summary["total_cost_usd"], 0)

    def test_get_run_summary_with_budget(self):
        """Test run summary with budget limits."""
        tracker = AgentCostTracker(
            metrics_path=self.metrics_path,
            max_cost_per_run=1.0,
            max_tokens_per_run=100000
        )
        tracker.reset_run_budget()

        tracker.record_execution(
            model="claude-4.5-haiku",
            phase="test",
            attempt_num=1,
            input_tokens=1000,
            output_tokens=500,
            duration_seconds=10.0,
            success=True,
            retry_count=0
        )

        summary = tracker.get_run_summary()

        self.assertIn("cost_budget_remaining_usd", summary)
        self.assertIn("cost_budget_used_percent", summary)
        self.assertIn("token_budget_remaining", summary)
        self.assertIn("token_budget_used_percent", summary)

    def test_persistence_save_and_load(self):
        """Test saving and loading metrics history."""
        tracker1 = AgentCostTracker(metrics_path=self.metrics_path)
        tracker1.reset_run_budget()

        tracker1.record_execution(
            model="claude-4.5-haiku",
            phase="test",
            attempt_num=1,
            input_tokens=1000,
            output_tokens=500,
            duration_seconds=10.0,
            success=True,
            retry_count=0
        )

        # Create new tracker with same path - should load history
        tracker2 = AgentCostTracker(metrics_path=self.metrics_path)

        self.assertEqual(len(tracker2.history), 1)
        self.assertEqual(tracker2.history[0].input_tokens, 1000)
        self.assertEqual(tracker2.history[0].output_tokens, 500)

    def test_get_total_cost(self):
        """Test getting total cost across all runs."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        tracker.reset_run_budget()

        # Record multiple executions
        for i in range(3):
            tracker.record_execution(
                model="claude-4.5-haiku",
                phase="test",
                attempt_num=i+1,
                input_tokens=1000,
                output_tokens=500,
                duration_seconds=10.0,
                success=True,
                retry_count=0
            )

        total_cost = tracker.get_total_cost()
        self.assertGreater(total_cost, 0)
        # Each execution costs 0.0035, so 3 * 0.0035 = 0.0105
        self.assertAlmostEqual(total_cost, 0.0105, places=6)

    def test_get_cost_by_model(self):
        """Test getting cost breakdown by model."""
        tracker = AgentCostTracker(metrics_path=self.metrics_path)
        tracker.reset_run_budget()

        # Record executions with different models
        tracker.record_execution(
            model="claude-4.5-haiku",
            phase="test",
            attempt_num=1,
            input_tokens=1000,
            output_tokens=500,
            duration_seconds=10.0,
            success=True,
            retry_count=0
        )

        tracker.record_execution(
            model="claude-4.5-sonnet",
            phase="test",
            attempt_num=2,
            input_tokens=2000,
            output_tokens=1000,
            duration_seconds=15.0,
            success=True,
            retry_count=0
        )

        breakdown = tracker.get_cost_by_model()

        self.assertIn("claude-4.5-haiku", breakdown)
        self.assertIn("claude-4.5-sonnet", breakdown)
        self.assertGreater(breakdown["claude-4.5-sonnet"], breakdown["claude-4.5-haiku"])


class TestParseClaudeTokens(unittest.TestCase):
    """Tests for parse_claude_tokens function."""

    def test_parse_standard_format(self):
        """Test parsing standard Claude output format."""
        output = "Input tokens: 1234, Output tokens: 5678"
        result = parse_claude_tokens(output)

        self.assertIsNotNone(result)
        self.assertEqual(result, (1234, 5678))

    def test_parse_alternate_format(self):
        """Test parsing alternate format."""
        output = "Tokens: 1234 in, 5678 out"
        result = parse_claude_tokens(output)

        self.assertIsNotNone(result)
        self.assertEqual(result, (1234, 5678))

    def test_parse_verbose_format(self):
        """Test parsing verbose format."""
        output = "Used 1234 input tokens and 5678 output tokens"
        result = parse_claude_tokens(output)

        self.assertIsNotNone(result)
        self.assertEqual(result, (1234, 5678))

    def test_parse_no_tokens(self):
        """Test parsing output with no token information."""
        output = "This is some output without token counts"
        result = parse_claude_tokens(output)

        self.assertIsNone(result)

    def test_parse_case_insensitive(self):
        """Test case insensitive parsing."""
        output = "INPUT TOKENS: 1234, OUTPUT TOKENS: 5678"
        result = parse_claude_tokens(output)

        self.assertIsNotNone(result)
        self.assertEqual(result, (1234, 5678))

    def test_parse_multiline_output(self):
        """Test parsing from multiline output."""
        output = """
        Some output here
        Input tokens: 1234, Output tokens: 5678
        More output here
        """
        result = parse_claude_tokens(output)

        self.assertIsNotNone(result)
        self.assertEqual(result, (1234, 5678))


if __name__ == "__main__":
    unittest.main()

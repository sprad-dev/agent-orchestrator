#!/usr/bin/env python3
"""Example demonstrating cost/token budget tracking and enforcement.

This example shows how to:
1. Set cost and token budgets
2. Track agent execution costs
3. Enforce budget limits that abort execution
4. View cost summaries and breakdowns
"""

from src.models import EscalationExecutor
from src.models.cost_tracker import AgentCostTracker


def example_with_cost_budget():
    """Example: Set a cost budget and abort if exceeded."""
    print("=== Example 1: Cost Budget ===\n")

    executor = EscalationExecutor(
        agent_cmd_template="echo 'Mock agent: {prompt}'",
        verify_cmd="echo 'Mock verify'",
        models=["claude-4.5-haiku", "claude-4.5-sonnet"],
        max_cost_per_run=0.50  # Max $0.50 per run
    )

    print(f"Cost Budget: ${executor.max_cost_per_run}")
    print("Execution will abort if cost exceeds budget.\n")


def example_with_token_budget():
    """Example: Set a token budget and abort if exceeded."""
    print("=== Example 2: Token Budget ===\n")

    executor = EscalationExecutor(
        agent_cmd_template="echo 'Mock agent: {prompt}'",
        verify_cmd="echo 'Mock verify'",
        models=["claude-4.5-haiku"],
        max_tokens_per_run=100000  # Max 100k tokens per run
    )

    print(f"Token Budget: {executor.max_tokens_per_run:,} tokens")
    print("Execution will abort if tokens exceed budget.\n")


def example_with_both_budgets():
    """Example: Set both cost and token budgets."""
    print("=== Example 3: Both Budgets ===\n")

    executor = EscalationExecutor(
        agent_cmd_template="echo 'Mock agent: {prompt}'",
        verify_cmd="echo 'Mock verify'",
        models=["claude-4.5-haiku", "claude-4.5-sonnet"],
        max_cost_per_run=1.00,     # Max $1.00 per run
        max_tokens_per_run=200000  # Max 200k tokens per run
    )

    print(f"Cost Budget: ${executor.max_cost_per_run}")
    print(f"Token Budget: {executor.max_tokens_per_run:,} tokens")
    print("Execution will abort if either budget is exceeded.\n")


def example_cost_tracking():
    """Example: Track costs without enforcing budgets."""
    print("=== Example 4: Cost Tracking (No Limits) ===\n")

    # Create tracker without budget limits
    tracker = AgentCostTracker(metrics_path=".example_metrics.json")
    tracker.reset_run_budget()

    # Simulate some agent executions
    print("Simulating agent executions...\n")

    # Execution 1: Haiku model
    tracker.record_execution(
        model="claude-4.5-haiku",
        phase="escalation",
        attempt_num=1,
        input_tokens=5000,
        output_tokens=2000,
        duration_seconds=12.5,
        success=False,
        retry_count=0
    )
    print("Attempt 1 (Haiku): 5000 input + 2000 output tokens")

    # Execution 2: Sonnet model (escalated)
    tracker.record_execution(
        model="claude-4.5-sonnet",
        phase="escalation",
        attempt_num=2,
        input_tokens=5000,
        output_tokens=3000,
        duration_seconds=18.3,
        success=True,
        retry_count=0
    )
    print("Attempt 2 (Sonnet): 5000 input + 3000 output tokens")

    # Get summary
    summary = tracker.get_run_summary()

    print("\n--- Run Summary ---")
    print(f"Total Cost: ${summary['total_cost_usd']:.4f}")
    print(f"Total Tokens: {summary['total_tokens']:,}")

    # Get cost by model
    by_model = tracker.get_cost_by_model()
    print("\nCost Breakdown by Model:")
    for model, cost in sorted(by_model.items(), key=lambda x: x[1], reverse=True):
        print(f"  {model}: ${cost:.4f}")


def example_cli_usage():
    """Example: Using budget limits from CLI."""
    print("\n=== Example 5: CLI Usage ===\n")

    print("Set budget limits from command line:")
    print()
    print("  # Cost budget of $0.50")
    print("  python supervisor.py 'Fix the bug' --max-cost 0.50")
    print()
    print("  # Token budget of 100k")
    print("  python supervisor.py 'Add feature' --max-tokens 100000")
    print()
    print("  # Both budgets")
    print("  python supervisor.py 'Refactor code' --max-cost 1.00 --max-tokens 200000")
    print()


if __name__ == "__main__":
    print("Cost and Token Budget Tracking Examples")
    print("=" * 50)
    print()

    example_with_cost_budget()
    example_with_token_budget()
    example_with_both_budgets()
    example_cost_tracking()
    example_cli_usage()

    print("\nFor more information, see:")
    print("  - src/models/cost_tracker.py")
    print("  - test_cost_tracker.py")

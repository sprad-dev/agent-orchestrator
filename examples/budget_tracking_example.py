#!/usr/bin/env python3
"""Example demonstrating cost/token budget tracking and execution logging.

This example shows how to:
1. Set cost and token budgets
2. Track agent execution costs and outcomes
3. Enforce budget limits that abort execution
4. View cost summaries and breakdowns
5. Analyze success rates and failure patterns
6. Query execution statistics
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    tracker = AgentCostTracker(metrics_path=".example_metrics.jsonl")
    tracker.reset_run_budget()

    # Simulate some agent executions
    print("Simulating agent executions...\n")

    # Execution 1: Haiku model (failed)
    tracker.record_execution(
        model="claude-4.5-haiku",
        phase="escalation",
        attempt_num=1,
        input_tokens=5000,
        output_tokens=2000,
        duration_seconds=12.5,
        outcome="fail",
        task_description="Fix authentication bug",
        failure_reason="test_fail",
        retry_count=0
    )
    print("Attempt 1 (Haiku): Failed - test_fail")

    # Execution 2: Sonnet model (escalated, successful)
    tracker.record_execution(
        model="claude-4.5-sonnet",
        phase="escalation",
        attempt_num=2,
        input_tokens=5000,
        output_tokens=3000,
        duration_seconds=18.3,
        outcome="success",
        task_description="Fix authentication bug",
        retry_count=0
    )
    print("Attempt 2 (Sonnet): Success!")

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


def example_execution_stats():
    """Example: Analyze execution statistics and patterns."""
    print("\n=== Example 5: Execution Statistics ===\n")

    # Create tracker and simulate diverse executions
    tracker = AgentCostTracker(metrics_path=".example_stats.jsonl")
    tracker.reset_run_budget()

    print("Simulating multiple executions...\n")

    # Mix of successes and failures
    executions = [
        ("claude-4.5-haiku", "success", None, "Implement login form"),
        ("claude-4.5-haiku", "fail", "test_fail", "Add validation"),
        ("claude-4.5-sonnet", "success", None, "Add validation"),
        ("claude-4.5-haiku", "fail", "timeout", "Fix database query"),
        ("claude-4.5-sonnet", "success", None, "Fix database query"),
        ("claude-4.5-haiku", "partial", "syntax_error", "Refactor API"),
    ]

    for i, (model, outcome, failure_reason, task) in enumerate(executions, 1):
        tracker.record_execution(
            model=model,
            phase="implementation",
            attempt_num=i,
            input_tokens=2000,
            output_tokens=1000,
            duration_seconds=15.0,
            outcome=outcome,
            task_description=task,
            failure_reason=failure_reason,
            retry_count=0
        )

    # Get success rate
    success_stats = tracker.get_success_rate()
    print(f"Overall Success Rate: {success_stats['success_rate']:.1f}%")
    print(f"  Successes: {success_stats['success_count']}")
    print(f"  Failures: {success_stats['fail_count']}")
    print(f"  Partial: {success_stats['partial_count']}")

    # Get stats by model
    model_stats = tracker.get_stats_by_model()
    print("\nPerformance by Model:")
    for model, stats in sorted(model_stats.items(), key=lambda x: x[1]['success_rate'], reverse=True):
        print(f"  {model}: {stats['success_rate']:.1f}% success ({stats['success_count']}/{stats['total_executions']})")

    # Get failure breakdown
    failures = tracker.get_failure_breakdown()
    if failures:
        print("\nFailure Reasons:")
        for reason, count in sorted(failures.items(), key=lambda x: x[1], reverse=True):
            print(f"  {reason}: {count}")


def example_cli_usage():
    """Example: Using budget limits and stats from CLI."""
    print("\n=== Example 6: CLI Usage ===\n")

    print("Set budget limits from command line:")
    print()
    print("  # Cost budget of $0.50")
    print("  ./supervisor.py 'Fix the bug' --max-cost 0.50")
    print()
    print("  # Token budget of 100k")
    print("  ./supervisor.py 'Add feature' --max-tokens 100000")
    print()
    print("  # Both budgets")
    print("  ./supervisor.py 'Refactor code' --max-cost 1.00 --max-tokens 200000")
    print()
    print("\nView execution statistics:")
    print()
    print("  # All-time statistics")
    print("  ./supervisor.py --stats")
    print()
    print("  # Last 7 days")
    print("  ./supervisor.py --stats --stats-days=7")
    print()
    print("  # Last 30 days")
    print("  ./supervisor.py --stats --stats-days=30")
    print()


if __name__ == "__main__":
    print("Cost/Token Budget Tracking & Execution Logging Examples")
    print("=" * 60)
    print()

    example_with_cost_budget()
    example_with_token_budget()
    example_with_both_budgets()
    example_cost_tracking()
    example_execution_stats()
    example_cli_usage()

    print("\nFor more information, see:")
    print("  - src/models/cost_tracker.py")
    print("  - test_cost_tracker.py")
    print("  - ./supervisor.py --stats")

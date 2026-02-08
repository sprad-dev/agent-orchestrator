"""Agent cost and token tracking for execution budget enforcement.

Track token usage and API costs per agent run. Support configurable budget
limits that abort execution when exceeded. Store historical metrics for
cost analysis and optimization.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


# Model pricing per million tokens (as of 2025)
# https://www.anthropic.com/pricing
MODEL_PRICING = {
    "claude-4.5-haiku": {"input": 1.00, "output": 5.00},
    "claude-4.5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-4.5-opus": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},  # Alias
    "claude-opus-4-5": {"input": 15.00, "output": 75.00},   # Alias
}


@dataclass
class CostMetrics:
    """Metrics for a single agent execution."""
    timestamp: str
    model: str
    phase: str  # "escalation", "test_generation", "implementation"
    attempt_num: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    duration_seconds: float
    outcome: str  # "success" | "partial" | "fail"
    task_description: str = ""
    failure_reason: Optional[str] = None  # timeout | budget | test_fail | syntax_error | integration_gap | etc.
    retry_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class BudgetExceededException(Exception):
    """Raised when execution budget is exceeded."""
    pass


class AgentCostTracker:
    """Track and enforce agent execution costs and token budgets."""

    def __init__(
        self,
        metrics_path: str = ".agent_execution_log.jsonl",
        max_cost_per_run: Optional[float] = None,
        max_tokens_per_run: Optional[int] = None
    ):
        """Initialize cost tracker.

        Args:
            metrics_path: Path to JSONL file for storing execution history
            max_cost_per_run: Maximum allowed cost in USD per run (None = no limit)
            max_tokens_per_run: Maximum allowed tokens per run (None = no limit)
        """
        self.metrics_path = Path(metrics_path)
        self.max_cost_per_run = max_cost_per_run
        self.max_tokens_per_run = max_tokens_per_run
        self.history: List[CostMetrics] = []
        self.current_run_cost = 0.0
        self.current_run_tokens = 0
        self._load_history()

    def _load_history(self) -> None:
        """Load execution history from JSONL file."""
        if self.metrics_path.exists():
            try:
                with open(self.metrics_path, 'r') as f:
                    self.history = []
                    for line in f:
                        line = line.strip()
                        if line:
                            entry = json.loads(line)
                            self.history.append(CostMetrics(**entry))
            except (json.JSONDecodeError, TypeError):
                # Corrupted or invalid file, start fresh
                self.history = []

    def _save_history(self) -> None:
        """Save execution history to JSONL file."""
        with open(self.metrics_path, 'w') as f:
            for entry in self.history:
                f.write(json.dumps(entry.to_dict()) + '\n')

    def reset_run_budget(self) -> None:
        """Reset current run cost/token counters."""
        self.current_run_cost = 0.0
        self.current_run_tokens = 0

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage.

        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        # Normalize model name
        model_key = model.lower()
        for key in MODEL_PRICING:
            if key in model_key:
                pricing = MODEL_PRICING[key]
                cost = (
                    (input_tokens / 1_000_000) * pricing["input"] +
                    (output_tokens / 1_000_000) * pricing["output"]
                )
                return cost

        # Unknown model - use Sonnet pricing as default
        pricing = MODEL_PRICING["claude-4.5-sonnet"]
        cost = (
            (input_tokens / 1_000_000) * pricing["input"] +
            (output_tokens / 1_000_000) * pricing["output"]
        )
        return cost

    def record_execution(
        self,
        model: str,
        phase: str,
        attempt_num: int,
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float,
        success: bool = None,
        outcome: str = None,
        task_description: str = "",
        failure_reason: Optional[str] = None,
        retry_count: int = 0
    ) -> CostMetrics:
        """Record metrics for an agent execution.

        Args:
            model: Model identifier
            phase: Execution phase (escalation, test_generation, implementation)
            attempt_num: Attempt number in current run
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            duration_seconds: Execution duration
            success: DEPRECATED - use outcome instead. Whether execution succeeded (for backwards compatibility)
            outcome: Execution outcome: "success" | "partial" | "fail"
            task_description: Brief description of the task being executed
            failure_reason: Reason for failure (timeout | budget | test_fail | syntax_error | integration_gap | etc.)
            retry_count: Number of retries for this execution

        Returns:
            CostMetrics object

        Raises:
            BudgetExceededException: If budget limits are exceeded
        """
        # Backwards compatibility: if success is provided but not outcome, convert it
        if outcome is None and success is not None:
            outcome = "success" if success else "fail"
        elif outcome is None:
            outcome = "unknown"

        total_tokens = input_tokens + output_tokens
        cost = self.calculate_cost(model, input_tokens, output_tokens)

        # Update current run counters
        self.current_run_cost += cost
        self.current_run_tokens += total_tokens

        # Check budget limits BEFORE recording (fail fast)
        if self.max_cost_per_run and self.current_run_cost > self.max_cost_per_run:
            raise BudgetExceededException(
                f"Cost budget exceeded: ${self.current_run_cost:.4f} > ${self.max_cost_per_run:.4f}"
            )

        if self.max_tokens_per_run and self.current_run_tokens > self.max_tokens_per_run:
            raise BudgetExceededException(
                f"Token budget exceeded: {self.current_run_tokens} > {self.max_tokens_per_run}"
            )

        # Record metrics
        metrics = CostMetrics(
            timestamp=datetime.now().isoformat(),
            model=model,
            phase=phase,
            attempt_num=attempt_num,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            duration_seconds=duration_seconds,
            outcome=outcome,
            task_description=task_description,
            failure_reason=failure_reason,
            retry_count=retry_count
        )

        self.history.append(metrics)
        self._save_history()

        return metrics

    def get_run_summary(self) -> Dict[str, float]:
        """Get summary of current run costs.

        Returns:
            Dict with total_cost, total_tokens, budget_remaining
        """
        summary = {
            "total_cost_usd": self.current_run_cost,
            "total_tokens": self.current_run_tokens,
        }

        if self.max_cost_per_run:
            summary["cost_budget_remaining_usd"] = max(0, self.max_cost_per_run - self.current_run_cost)
            summary["cost_budget_used_percent"] = (self.current_run_cost / self.max_cost_per_run) * 100

        if self.max_tokens_per_run:
            summary["token_budget_remaining"] = max(0, self.max_tokens_per_run - self.current_run_tokens)
            summary["token_budget_used_percent"] = (self.current_run_tokens / self.max_tokens_per_run) * 100

        return summary

    def get_total_cost(self, days: Optional[int] = None) -> float:
        """Get total cost across all runs.

        Args:
            days: If specified, only count last N days

        Returns:
            Total cost in USD
        """
        if days is None:
            return sum(m.estimated_cost_usd for m in self.history)

        # Filter by date
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        recent = [
            m for m in self.history
            if datetime.fromisoformat(m.timestamp) > cutoff
        ]
        return sum(m.estimated_cost_usd for m in recent)

    def get_cost_by_model(self, days: Optional[int] = None) -> Dict[str, float]:
        """Get cost breakdown by model.

        Args:
            days: If specified, only count last N days

        Returns:
            Dict of model -> total cost
        """
        if days is not None:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)
            metrics = [
                m for m in self.history
                if datetime.fromisoformat(m.timestamp) > cutoff
            ]
        else:
            metrics = self.history

        breakdown = {}
        for m in metrics:
            breakdown[m.model] = breakdown.get(m.model, 0.0) + m.estimated_cost_usd

        return breakdown

    def get_success_rate(self, days: Optional[int] = None) -> Dict[str, float]:
        """Get success rate statistics.

        Args:
            days: If specified, only count last N days

        Returns:
            Dict with success_rate, total_executions, success_count, fail_count, partial_count
        """
        if days is not None:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)
            metrics = [
                m for m in self.history
                if datetime.fromisoformat(m.timestamp) > cutoff
            ]
        else:
            metrics = self.history

        if not metrics:
            return {
                "total_executions": 0,
                "success_count": 0,
                "fail_count": 0,
                "partial_count": 0,
                "success_rate": 0.0
            }

        success_count = sum(1 for m in metrics if m.outcome == "success")
        fail_count = sum(1 for m in metrics if m.outcome == "fail")
        partial_count = sum(1 for m in metrics if m.outcome == "partial")
        total = len(metrics)

        return {
            "total_executions": total,
            "success_count": success_count,
            "fail_count": fail_count,
            "partial_count": partial_count,
            "success_rate": (success_count / total * 100) if total > 0 else 0.0
        }

    def get_stats_by_model(self, days: Optional[int] = None) -> Dict[str, Dict]:
        """Get success rate and cost breakdown by model.

        Args:
            days: If specified, only count last N days

        Returns:
            Dict of model -> {success_rate, total_executions, total_cost}
        """
        if days is not None:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)
            metrics = [
                m for m in self.history
                if datetime.fromisoformat(m.timestamp) > cutoff
            ]
        else:
            metrics = self.history

        breakdown = {}
        for m in metrics:
            if m.model not in breakdown:
                breakdown[m.model] = {
                    "total_executions": 0,
                    "success_count": 0,
                    "total_cost": 0.0
                }

            breakdown[m.model]["total_executions"] += 1
            if m.outcome == "success":
                breakdown[m.model]["success_count"] += 1
            breakdown[m.model]["total_cost"] += m.estimated_cost_usd

        # Calculate success rates
        for model, stats in breakdown.items():
            total = stats["total_executions"]
            success = stats["success_count"]
            stats["success_rate"] = (success / total * 100) if total > 0 else 0.0

        return breakdown

    def get_failure_breakdown(self, days: Optional[int] = None) -> Dict[str, int]:
        """Get breakdown of failure reasons.

        Args:
            days: If specified, only count last N days

        Returns:
            Dict of failure_reason -> count
        """
        if days is not None:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)
            metrics = [
                m for m in self.history
                if datetime.fromisoformat(m.timestamp) > cutoff
            ]
        else:
            metrics = self.history

        breakdown = {}
        for m in metrics:
            if m.failure_reason:
                breakdown[m.failure_reason] = breakdown.get(m.failure_reason, 0) + 1

        return breakdown

    def print_stats(self, days: Optional[int] = None) -> None:
        """Print comprehensive execution statistics.

        Args:
            days: If specified, only show last N days (default: all time)
        """
        period = f"Last {days} days" if days else "All time"
        print(f"\n=== EXECUTION STATISTICS ({period}) ===\n")

        # Overall success rate
        success_stats = self.get_success_rate(days)
        print(f"Overall Success Rate: {success_stats['success_rate']:.1f}%")
        print(f"  Total Executions: {success_stats['total_executions']}")
        print(f"  Successes: {success_stats['success_count']}")
        print(f"  Failures: {success_stats['fail_count']}")
        print(f"  Partial: {success_stats['partial_count']}")

        # Cost summary
        total_cost = self.get_total_cost(days)
        print(f"\nTotal Cost: ${total_cost:.4f}")

        # Model breakdown
        model_stats = self.get_stats_by_model(days)
        if model_stats:
            print("\n--- Performance by Model ---")
            for model, stats in sorted(model_stats.items(), key=lambda x: x[1]['total_cost'], reverse=True):
                print(f"\n{model}:")
                print(f"  Success Rate: {stats['success_rate']:.1f}%")
                print(f"  Executions: {stats['total_executions']}")
                print(f"  Total Cost: ${stats['total_cost']:.4f}")

        # Failure breakdown
        failures = self.get_failure_breakdown(days)
        if failures:
            print("\n--- Failure Reasons ---")
            for reason, count in sorted(failures.items(), key=lambda x: x[1], reverse=True):
                print(f"  {reason}: {count}")

        print()


def parse_claude_tokens(output: str) -> Optional[Tuple[int, int]]:
    """Parse token usage from Claude CLI output.

    The Claude CLI outputs token usage in formats like:
    - "Input tokens: 1234, Output tokens: 5678"
    - "Tokens: 1234 in, 5678 out"

    Args:
        output: Claude CLI output string

    Returns:
        Tuple of (input_tokens, output_tokens), or None if not found
    """
    # Try various patterns
    patterns = [
        r'Input tokens:\s*(\d+),?\s*Output tokens:\s*(\d+)',
        r'Tokens:\s*(\d+)\s*in,?\s*(\d+)\s*out',
        r'(\d+)\s*input.*?(\d+)\s*output',
    ]

    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            input_tokens = int(match.group(1))
            output_tokens = int(match.group(2))
            return input_tokens, output_tokens

    return None

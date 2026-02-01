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
    success: bool
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
        metrics_path: str = ".agent_cost_metrics.json",
        max_cost_per_run: Optional[float] = None,
        max_tokens_per_run: Optional[int] = None
    ):
        """Initialize cost tracker.

        Args:
            metrics_path: Path to JSON file for storing cost history
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
        """Load cost history from JSON file."""
        if self.metrics_path.exists():
            try:
                with open(self.metrics_path, 'r') as f:
                    data = json.load(f)
                    self.history = [CostMetrics(**entry) for entry in data]
            except (json.JSONDecodeError, TypeError):
                # Corrupted or invalid file, start fresh
                self.history = []

    def _save_history(self) -> None:
        """Save cost history to JSON file."""
        with open(self.metrics_path, 'w') as f:
            data = [entry.to_dict() for entry in self.history]
            json.dump(data, f, indent=2)

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
        success: bool,
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
            success: Whether execution succeeded
            retry_count: Number of retries for this execution

        Returns:
            CostMetrics object

        Raises:
            BudgetExceededException: If budget limits are exceeded
        """
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
            success=success,
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

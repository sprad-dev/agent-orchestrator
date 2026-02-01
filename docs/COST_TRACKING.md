# Cost and Token Budget Tracking

## Overview

The agent orchestrator now tracks token usage and API costs for all agent executions, with optional budget limits that automatically abort execution when exceeded.

## Quick Start

### Set Cost Budget

```bash
# Abort if execution costs exceed $0.50
python supervisor.py "Add feature" --max-cost 0.50
```

### Set Token Budget

```bash
# Abort if execution uses more than 100k tokens
python supervisor.py "Fix bug" --max-tokens 100000
```

### Set Both Budgets

```bash
# Abort if either limit is exceeded
python supervisor.py "Refactor code" --max-cost 1.00 --max-tokens 200000
```

## How It Works

### Automatic Tracking

Every agent execution is automatically tracked:
- Input tokens consumed
- Output tokens generated
- Total tokens used
- Estimated cost (based on Anthropic pricing)
- Execution duration
- Success/failure status

### Budget Enforcement

When budget limits are set:
1. Token usage is parsed from Claude CLI output
2. Costs are calculated based on model pricing
3. Running totals are maintained for the current run
4. If budget is exceeded, execution aborts immediately
5. Git state is reverted to clean state
6. Summary shows budget usage

### Cost Calculation

Costs are calculated using current Anthropic API pricing:

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| Haiku | $1.00 | $5.00 |
| Sonnet | $3.00 | $15.00 |
| Opus | $15.00 | $75.00 |

**Example:**
- 10,000 input tokens + 5,000 output tokens with Haiku
- Cost = (10,000/1M × $1) + (5,000/1M × $5) = $0.01 + $0.025 = $0.035

## Execution Summary

At the end of execution, you'll see a detailed summary:

```
--- EXECUTION SUMMARY ---
Total Duration: 45.2s
Total Cost: $0.0285
Total Tokens: 12,450
Cost Budget Used: 57.0% ($0.0215 remaining)
Token Budget Used: 12.5% (87,550 remaining)

Cost by Model:
  claude-4.5-sonnet: $0.0210
  claude-4.5-haiku: $0.0075
```

## Historical Data

All executions are logged to `.agent_cost_metrics.json`:

```json
[
  {
    "timestamp": "2025-01-31T15:30:45.123456",
    "model": "claude-4.5-haiku",
    "phase": "escalation",
    "attempt_num": 1,
    "input_tokens": 5000,
    "output_tokens": 2000,
    "total_tokens": 7000,
    "estimated_cost_usd": 0.015,
    "duration_seconds": 12.5,
    "success": true,
    "retry_count": 0
  }
]
```

## Programmatic Usage

### Using the Cost Tracker Directly

```python
from src.models.cost_tracker import AgentCostTracker, BudgetExceededException

# Initialize with budget limits
tracker = AgentCostTracker(
    max_cost_per_run=1.0,
    max_tokens_per_run=100000
)
tracker.reset_run_budget()

# Record an execution
try:
    metrics = tracker.record_execution(
        model="claude-4.5-haiku",
        phase="implementation",
        attempt_num=1,
        input_tokens=5000,
        output_tokens=2000,
        duration_seconds=12.5,
        success=True,
        retry_count=0
    )
except BudgetExceededException as e:
    print(f"Budget exceeded: {e}")
    # Handle budget exceeded

# Get summary
summary = tracker.get_run_summary()
print(f"Total cost: ${summary['total_cost_usd']:.4f}")
print(f"Total tokens: {summary['total_tokens']:,}")
```

### Using with Executors

```python
from src.models import EscalationExecutor

executor = EscalationExecutor(
    agent_cmd_template="claude {prompt}",
    verify_cmd="pytest",
    models=["claude-4.5-haiku", "claude-4.5-sonnet"],
    max_cost_per_run=0.50,      # $0.50 budget
    max_tokens_per_run=100000   # 100k token budget
)

success = executor.execute("Add user authentication")
```

## Benefits

### Cost Control
- Prevent runaway costs with hard limits
- Fail fast when budget is exceeded
- No surprises on your API bill

### Visibility
- See exactly how much each task costs
- Understand token consumption patterns
- Identify expensive operations

### Optimization
- Compare costs across different models
- Find opportunities to use cheaper models
- Track improvements over time

### Budgeting
- Plan agent execution costs in advance
- Set per-task budgets
- Monitor spending trends

## Implementation Details

### Architecture

The cost tracking system consists of:

1. **`AgentCostTracker`** (`src/models/cost_tracker.py`)
   - Tracks token usage and costs
   - Enforces budget limits
   - Persists metrics to JSON

2. **Shell Executor Integration** (`src/shell/executor.py`)
   - `run_shell_with_retry()` accepts optional cost tracker
   - Parses tokens from Claude CLI output
   - Records metrics after each execution

3. **Executor Integration** (`src/models/escalation.py`, `src/models/two_phase.py`)
   - Initializes cost tracker with budget limits
   - Passes tracker to shell executor
   - Handles `BudgetExceededException`
   - Prints cost summary

4. **CLI Support** (`supervisor.py`)
   - `--max-cost`: Set cost budget in USD
   - `--max-tokens`: Set token budget

### Token Parsing

The system parses token usage from Claude CLI output using regex patterns:
- "Input tokens: 1234, Output tokens: 5678"
- "Tokens: 1234 in, 5678 out"
- "1234 input, 5678 output"

### Budget Checking

Budget is checked **before** recording each execution:
1. Parse tokens from output
2. Calculate cost
3. Add to running total
4. Check if budget exceeded
5. If exceeded, raise `BudgetExceededException`
6. Otherwise, record metrics

This ensures execution aborts immediately when budget is exceeded.

## Testing

Comprehensive test suite in `test_cost_tracker.py`:
- 23 unit tests
- Cost calculation for all models
- Budget enforcement (cost and tokens)
- Token parsing
- Persistence (save/load)
- Historical analysis

Run tests:
```bash
python -m pytest test_cost_tracker.py -v
```

## Examples

See `examples/budget_tracking_example.py` for detailed usage examples.

## Future Enhancements

Potential improvements:
- Budget alerts at thresholds (e.g., 50%, 75%)
- Cost forecasting based on historical data
- Per-model budget limits
- Budget pooling across multiple runs
- Integration with billing APIs for actual costs
- Cost optimization recommendations

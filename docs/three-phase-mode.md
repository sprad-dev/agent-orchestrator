# Three-Phase Execution Mode (Adversarial Review)

## Overview

Three-phase mode extends the two-phase architect/intern pattern with an **Adversary** agent that reviews test quality and writes hardening tests. This catches shallow test coverage through automated mutation testing via adversarial prompting.

## How It Works

### Execution Flow

1. **Phase 1: Architect** writes initial tests (smart model)
2. **Phase 2: Intern** implements code to pass tests (cheap model)
3. **Phase 3: Adversary** reviews test quality and writes hardening tests (smart model)
4. **Phase 4: Intern** implements code to pass hardening tests (cheap model)

### What the Adversary Checks

The Adversary identifies common test quality issues:
- **Hardcoded returns**: Tests that pass with stub implementations (`return 42`)
- **Mock-only assertions**: Tests that only verify mocks were called, not actual behavior
- **Untested error paths**: Missing tests for exceptions, edge cases, invalid inputs
- **Missing edge cases**: No tests for empty inputs, boundary values, special characters

### Cost vs. Benefit

- **Cost**: ~30-50% more tokens per task (one additional architect-level call + one intern call)
- **Benefit**: Catches shallow coverage that would otherwise pass verification
- **Recommended**: Use for critical code paths, complex business logic, or when test quality is paramount

## Usage

### Command Line

```bash
# Enable three-phase mode with --adversary-model flag
./supervisor.py "Add user authentication" \
  --test-model claude-4.5-sonnet \
  --impl-model claude-4.5-haiku \
  --adversary-model claude-4.5-sonnet \
  --verify pytest
```

### Python API

```python
from src.models import ThreePhaseExecutor

executor = ThreePhaseExecutor(
    agent_cmd_template="claude {prompt}",
    verify_cmd="pytest",
    test_model="claude-4.5-sonnet",      # Architect
    impl_model="claude-4.5-haiku",        # Intern
    adversary_model="claude-4.5-sonnet"   # Adversary
)

success = executor.execute("Add user validation")
```

### Via RalphLoop

```python
from supervisor import RalphLoop

loop = RalphLoop(
    agent_cmd_template="claude {prompt}",
    verify_cmd="pytest",
    max_retries=3,
    test_model="claude-4.5-sonnet",
    impl_model="claude-4.5-haiku",
    adversary_model="claude-4.5-sonnet"  # Enables three-phase mode
)

success = loop.execute("Implement payment processing")
```

## Graceful Degradation

Three-phase mode gracefully handles edge cases:

- **No hardening tests needed**: If Adversary finds tests are already good, succeeds without Phase 4
- **Hardening tests already pass**: If hardening tests pass immediately, succeeds without Phase 4 implementation
- **Timeout before adversary**: Falls back to initial implementation (Phases 1-2 complete)
- **Hardening implementation fails**: Reverts hardening tests, keeps initial implementation

The initial implementation (Phases 1-2) is always preserved even if adversarial review fails.

## Example Scenarios

### Scenario 1: Shallow Tests Detected

```python
# Phase 1: Architect writes
def test_calculate_total():
    assert calculate_total([1, 2, 3]) == 6

# Phase 2: Intern implements (cheating!)
def calculate_total(items):
    return 6  # Hardcoded!

# Phase 3: Adversary adds hardening test
def test_calculate_total_not_hardcoded():
    assert calculate_total([10, 20]) == 30  # Fails with hardcoded return!

# Phase 4: Intern implements correctly
def calculate_total(items):
    return sum(items)  # Now correct
```

### Scenario 2: Missing Error Handling

```python
# Phase 1: Architect writes happy path only
def test_parse_json_valid():
    assert parse_json('{"key": "value"}') == {"key": "value"}

# Phase 2: Intern implements
def parse_json(text):
    return json.loads(text)  # No error handling!

# Phase 3: Adversary adds error path test
def test_parse_json_invalid_input():
    with pytest.raises(ValueError):
        parse_json("not json")  # Fails! No ValueError, just json.JSONDecodeError

# Phase 4: Intern adds error handling
def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
```

## When to Use

### Use Three-Phase Mode For:
- ✅ Critical business logic (payment, auth, data integrity)
- ✅ Complex algorithms with edge cases
- ✅ Code that handles user input or external data
- ✅ Security-sensitive operations
- ✅ When test quality is more important than speed/cost

### Use Two-Phase Mode For:
- 📝 Simple CRUD operations
- 📝 UI components with straightforward behavior
- 📝 Prototyping and experimentation
- 📝 Cost-sensitive environments
- 📝 When speed is more important than exhaustive testing

## Integration with Ralph Loop

Three-phase mode is fully compatible with the Ralph Loop pattern:
- Fresh context per phase (no conversation memory)
- Git commits after each phase (rollback-safe)
- Timeout enforcement across all phases
- Cost tracking per model (architect/intern/adversary breakdowns)

## Future Enhancements (Tier 1+)

- **Configurable adversary strategies**: Focus on specific weakness types
- **Adversary confidence scores**: Skip Phase 3/4 if initial tests score high
- **Multi-adversary rounds**: Multiple hardening iterations
- **Adversary-specific models**: Different model for adversarial review

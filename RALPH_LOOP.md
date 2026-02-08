# Ralph Loop

Implements Geoffrey Huntley's Ralph Loop pattern for agent task execution.

## Core Concept

**Progress persists through artifacts (git, files), not agent memory.**

Each iteration spawns a fresh agent with clean context. This prevents:
- Context degradation across retries
- Conversation history bloat
- Accumulated confusion from failed attempts

Progress is tracked through:
- Git commits
- File changes (the diff)
- Spec checklist (.ralph_spec.json)

## How It Works

```
1. Spawn fresh agent → Execute task → Verify
                             ↓ fail
2. Spawn fresh agent → Read git diff + spec → Fix → Verify
                                                 ↓ fail
3. Spawn fresh agent → Read git diff + spec → Fix → Verify
                                                 ↓ success
✓ Done
```

Each iteration:
- Gets a **clean context** (no conversation history)
- Reads **only** the original spec + current git diff
- Makes changes and commits
- Verification runs
- If incomplete: loop again with fresh context

## Usage

### Basic

```bash
./ralph_loop.py "Implement user authentication"
```

### With Budget Limits

```bash
./ralph_loop.py "Fix checkout bug" \
  --max-cost 0.50 \
  --max-iterations 3
```

### Custom Verification

```bash
./ralph_loop.py "Refactor API endpoints" \
  --verify "pytest tests/api/ -v"
```

### Full Example

```bash
./ralph_loop.py "Add email validation to signup form" \
  --max-iterations 5 \
  --max-cost 1.00 \
  --max-tokens 200000 \
  --verify "pytest tests/test_signup.py"
```

## Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `task` | Task description (required) | - |
| `--verify` | Verification command | `pytest` |
| `--max-iterations` | Max loop iterations | `5` |
| `--max-cost` | Max cost per iteration (USD) | None |
| `--max-tokens` | Max tokens per iteration | None |
| `--supervisor` | Path to supervisor.py | `./supervisor.py` |
| `--agent` | Primary agent command template | `claude {prompt}` |
| `--fallback-agents` | Comma-separated fallback agents | None |

## Fallback Agents

Ralph Loop supports fallback agents for when your primary LLM hits rate/usage limits.

### Basic Fallback

```bash
./ralph_loop.py "Implement feature" \
  --fallback-agents "gh copilot suggest -t shell {prompt}"
```

### Multiple Fallbacks

```bash
./ralph_loop.py "Complex task" \
  --agent "claude {prompt}" \
  --fallback-agents "gh copilot suggest -t shell {prompt},aider --yes --message {prompt}"
```

### How It Works

1. Primary agent runs first
2. If it hits a rate/usage limit, fallback is tried
3. Rate limit detection looks for:
   - `rate limit exceeded`
   - `usage limit`
   - `quota exceeded`
   - `429` status
   - `budget exceeded`

### Use Case: Budget Protection

Set a budget and automatically fall back to a cheaper model:

```bash
./ralph_loop.py "Large refactoring" \
  --max-cost 0.50 \
  --fallback-agents "gh copilot suggest -t shell {prompt}"
```

When Claude hits $0.50, Copilot takes over automatically.

See `agents/README.md` for more agent configurations.

## Exit Conditions

The loop terminates when:
1. ✓ **Success**: All verification passes
2. ✗ **Max iterations**: Reached iteration limit
3. ✗ **Budget exceeded**: Cost or token budget exceeded (all agents)

## Spec Tracking (Optional)

The loop can track explicit spec items:

```python
from ralph_loop import SpecTracker

tracker = SpecTracker()
tracker.add_item("Login form accepts email", check_cmd="pytest tests/test_login.py")
tracker.add_item("Validation shows errors", check_cmd="pytest tests/test_validation.py")
```

Items are saved to `.ralph_spec.json` and checked each iteration.

## Philosophy (Huntley's Insights)

1. **Artifacts beat memory**: Code changes persist in git. Conversation history doesn't.

2. **Fresh context prevents rot**: Each retry starts clean, reading only the diff + spec.

3. **Brute force persistence**: Keep trying with fresh perspectives until it works.

4. **Verification is truth**: Tests/checks determine progress, not agent claims.

## Comparison to Traditional Loops

| Traditional Retry | Ralph Loop |
|------------------|------------|
| Accumulated conversation | Fresh context each iteration |
| Context degradation | No degradation |
| Agent remembers failures | Agent sees only diff + spec |
| Relies on agent memory | Relies on git artifacts |

## Testing the Guinea Pig

Test on the real project:

```bash
cd /home/wspradley/src/investing/my-investing

# Pick a real task from beads
bd ready

# Run Ralph Loop
/home/wspradley/src/agent-orchestrator/ralph_loop.py \
  "Fix bug in LangGraph analysis agent" \
  --max-iterations 5 \
  --verify "pytest tests/"
```

## References

- [Geoffrey Huntley's Ralph Loop](https://ghuntley.com/loop/)
- [Ralph Plugin for Claude Code](https://github.com/snarktank/ralph)
- Steve Yegge's Gas Town (multi-agent orchestration)

## Related Files

- `ralph_loop.py` - Main implementation
- `test_ralph_loop.py` - Unit tests
- `supervisor.py` - Underlying execution engine
- `.ralph_spec.json` - Spec tracking (auto-generated)

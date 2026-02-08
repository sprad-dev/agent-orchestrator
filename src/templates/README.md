# Prompt Templates

Tier 0 backpressure mechanisms for agent quality enforcement.

## Overview

This module provides two core deliverables:

1. **Anti-pattern Suffix** — Quality gates appended to every task prompt
2. **Completion Manifest** — Structured proof of completeness required before marking tasks done

Both templates address the three failure modes identified in `docs/tier0-backpressure-deep-dive.md`:
- Shallow/useless tests
- Missing integration
- Hard-to-spot incompleteness

## Usage

### Automatic Integration

The templates are **automatically included** in all agent prompts via `src/context/builder.py`:

```python
from src.context import build_static_context

# Quality gates and completion manifest are included automatically
context, size = build_static_context(context_files)
```

### Manual Usage

You can also use the templates directly:

```python
from src.templates import (
    ANTI_PATTERN_SUFFIX,
    COMPLETION_MANIFEST_TEMPLATE,
    get_quality_gates,
    format_completion_manifest,
)

# Append quality gates to a custom prompt
prompt = f"{task_description}\n{ANTI_PATTERN_SUFFIX}"

# Generate a filled completion manifest
manifest = format_completion_manifest(
    files_created=[("src/feature.py", "New feature")],
    files_modified=[("src/main.py", "Integrated feature")],
    integration_points={'entrypoint': "Called from main.py:42"},
    tests_added={'unit': 5, 'integration': 2, 'edge_case': 3},
    delete_test={
        'deleted_files': ["src/feature.py"],
        'what_breaks': "test_integration.py would fail",
    },
    known_gaps=[],
)
```

## Anti-Pattern Suffix

Five quality gates enforced on every task:

1. **NO test-the-mock** — Assert on observable behavior, not mock calls
2. **NO orphan code** — Every new public type/method must be called from existing code
3. **NO happy-path-only** — Every success test needs a failure/edge test
4. **NO shallow assertions** — Assert on specific values, not just null checks
5. **WIRING PROOF** — List all modified files and integration points

### Language Adaptations

While the core gates apply to all languages, examples can be adapted:

**Python** (default):
```python
# BAD:  mock_service.save.assert_called_once()
# GOOD: assert result.status == "saved"
```

**C#**:
```csharp
// BAD:  mockService.Verify(x => x.Save(It.IsAny<User>()), Times.Once)
// GOOD: Assert.Equal("saved", result.Status)
```

**TypeScript**:
```typescript
// BAD:  expect(mockService.save).toHaveBeenCalledOnce()
// GOOD: expect(result.status).toBe("saved")
```

Use `get_quality_gates(language='csharp')` to get language-specific templates (future enhancement).

## Completion Manifest

Required sections:

1. **Files Created** — List with purpose for each
2. **Files Modified** — List with reason for each change
3. **Integration Points** — Where new code connects to existing system
4. **Tests Added** — Breakdown by type (unit, integration, edge case)
5. **Delete Test** — Proof of integration: "If I deleted X, Y would break"
6. **Known Gaps** — Explicit list of what's NOT covered (or "None")

### Verification

Use `parse_completion_manifest()` to verify agents actually filled out the manifest:

```python
from src.templates.completion_manifest import parse_completion_manifest

parsed = parse_completion_manifest(agent_output)
if parsed is None:
    # Agent just copy-pasted template without filling it out
    raise ValueError("Incomplete manifest")

print(f"Tests added: {parsed['total_tests']}")
print(f"Files created: {parsed['files_created_count']}")
```

## Integration with Ralph Loop

The templates work seamlessly with the Ralph Loop (`src/models/ralph_loop.py`):

- **Quality gates** constrain HOW the agent builds (no shortcuts)
- **Completion manifest** proves the agent FINISHED (no hidden gaps)
- **Fresh context per iteration** means gates are enforced every loop

This creates backpressure: the agent can't mark a task done until ALL gates pass AND the manifest proves completeness.

## Multi-Language Projects

For .NET/TypeScript day job repos:

1. Copy `src/templates/` to your repo
2. Update examples in `quality_gates.py` to match your language
3. Import and use in your orchestrator's prompt builder
4. Adjust test framework names (xUnit, Jest, etc.) in examples

The core gates and manifest structure are language-agnostic.

## Testing

Run tests:
```bash
pytest tests/test_templates.py -v
```

All tests verify:
- Templates contain all required sections
- Formatting functions work correctly
- Parsing detects unfilled templates
- Integration with context builder works

## References

- `docs/tier0-backpressure-deep-dive.md` — Full rationale and design
- `src/context/builder.py` — Automatic integration point
- `tests/test_templates.py` — Comprehensive test suite

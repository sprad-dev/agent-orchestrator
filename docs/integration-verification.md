# Integration Entrypoint Verification

Part of Tier 0: Backpressure & Verification mechanisms.

## Problem

A common agent failure mode: code exists, tests pass, but nothing calls it. The feature is "done" but unreachable from the application's entry points.

## Solution

The **Integration Check Layer (L4)** validates that new code is properly wired into the existing system by analyzing the completion manifest filled out by the agent.

## How It Works

### Check A: Integration Points Validation

The agent must document:
- **Entrypoint**: Exact location where new code is called (e.g., `api/routes.py:42`)
- **Registration**: Where new code is registered/wired (e.g., DI container, middleware)
- **Configuration**: Any config changes needed

If new files are created with no integration points and no existing files modified, the code is flagged as **orphaned**.

### Check B: Delete Test

The agent must answer: "If you deleted these files, what would break?"

Valid responses specify:
- Exact files that would be deleted
- Specific tests or behaviors that would fail
- How the failure would manifest (ImportError, 404, etc.)

Invalid responses:
- "Not applicable" when new files were created
- Placeholder text like "[these tests/behaviors]"
- Vague statements like "Unknown"

## Usage

### In Code

```python
from src.verification import IntegrationCheckLayer

# Basic usage
layer = IntegrationCheckLayer()
result = layer.run(manifest_text=completion_manifest)

# Strict mode (validates entrypoints exist in codebase)
layer = IntegrationCheckLayer(strict_mode=True)
result = layer.run(manifest_text=completion_manifest)
```

### In Configuration

```toml
# .verification.toml
[verification]
enable_integration_check = true
integration_strict_mode = false  # Set true to validate file paths
```

## Verification Flow

```
Phase 1: Test Generation
         ↓
Phase 2: Implementation
         ↓
Phase 3: Adversarial Review (optional)
         ↓
L1: File Exists ✓
         ↓
L2: Syntax Check ✓
         ↓
L3: Tests Pass ✓
         ↓
L4: Integration Check ✓  ← THIS LAYER
         ↓
Task Complete
```

## What Gets Checked

1. **Manifest Completeness**: Is the completion manifest filled out (not just template)?
2. **Integration Points**: Are entrypoints documented when new files are created?
3. **Delete Test**: Is the delete test filled out when new files are created?
4. **Placeholder Detection**: Are there generic placeholders instead of specific details?
5. **Optional: Static Validation** (strict mode): Do the referenced files/line numbers exist?

## Pass/Fail Examples

### ✓ PASS: Properly Integrated

```markdown
## Files Created
- [x] src/user_service.py — Purpose: User management service

## Files Modified
- [x] src/api/routes.py — Reason: Added POST /users endpoint
- [x] src/di/container.py — Reason: Registered UserService

## Integration Points
- [x] Entrypoint: Called from src/api/routes.py:42 in create_user()
- [x] Registration: Registered in src/di/container.py:15

## Delete Test
- [x] Deleted files: src/user_service.py
- [x] What breaks: test_api.py::test_create_user fails with ImportError,
     POST /api/users returns 500
```

### ✗ FAIL: Orphaned Code

```markdown
## Files Created
- [x] src/new_utility.py — Purpose: Helper functions

## Files Modified
- None

## Integration Points
- No integration points (pure library/utility)

## Delete Test
- Not applicable (no new files created)
```

**Why it fails**: New file created but not imported/called anywhere, and delete test incorrectly says "not applicable".

### ✗ FAIL: Placeholder Text

```markdown
## Delete Test
- [x] Deleted files: src/feature.py
- [x] What breaks: [these tests/behaviors] would fail
```

**Why it fails**: Agent didn't replace the placeholder `[these tests/behaviors]`.

## Design Rationale

### Why Not Automated Static Analysis?

We could use tools like `grep` or AST parsing to verify integration automatically. But:

1. **Language-specific complexity**: Works differently for Python, .NET, Node.js, etc.
2. **Indirect integration**: Code might be called via reflection, DI containers, config-based routing
3. **Agent accountability**: Forcing the agent to document integration makes it think about it

The current approach strikes a balance:
- Agents must **explicitly document** integration (forces intentionality)
- Validators **check documentation completeness** (catches copy-paste)
- Optional **strict mode** validates claims (verifies file paths exist)

### Why L4 Instead of L3?

Integration verification requires:
- Tests to pass (L3) first — can't verify integration if tests don't exist
- Completion manifest to be filled out — produced during implementation phase

So it runs **after** test verification but **before** considering the task complete.

## References

- Tier 0 Design: `docs/tier0-backpressure-deep-dive.md`
- Completion Manifest: `src/templates/completion_manifest.py`
- Quality Gates: `src/templates/quality_gates.py`

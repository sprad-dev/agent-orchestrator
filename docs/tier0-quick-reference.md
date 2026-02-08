# Tier 0 Quick Reference

> One-page reference for quality gates, completion manifest, and common patterns

## The 5 Quality Gates

| Gate | Rule | Bad Example | Good Example |
|------|------|-------------|--------------|
| **1. NO test-the-mock** | Assert on observable behavior, not mock interactions | `mock.save.assert_called()` | `assert result.status == "saved"` |
| **2. NO orphan code** | Every new public type/method must be called from existing code | Created UserService, nothing imports it | UserService called from routes.py:42 |
| **3. NO happy-path-only** | Every success test needs failure/edge test | Only `test_login_success()` | `test_login_success()` + `test_login_invalid_password()` |
| **4. NO shallow assertions** | Assert on specific values, not just null checks | `assert result is not None` | `assert result.id == 123` |
| **5. WIRING PROOF** | List every modified file and why | Only created new files | "Modified routes.py to add endpoint, container.py to register service" |

## Completion Manifest Checklist

```
Must include before task marked "done":

✓ Files Created — List with purpose for each
✓ Files Modified — List with reason for each change
✓ Integration Points — Where new code connects to existing
✓ Tests Added — Breakdown: unit/integration/edge (with counts)
✓ Delete Test — Proof: "If I deleted X, Y would break"
✓ Known Gaps — Explicit list of what's NOT done (or "None")
```

## Common Violations & Fixes

### Violation: Orphan Code (Gate 2)

```python
# ❌ PROBLEM
Files Created:
  + src/services/notification_service.py

Files Modified:
  [none]  # Nothing calls it!

# ✓ FIX
Files Modified:
  + src/api/routes.py — Line 45: imported NotificationService,
                        Line 89: calls notify() on order creation
  + src/di/container.py — Line 12: registered NotificationService
```

### Violation: Shallow Tests (Gate 4)

```python
# ❌ PROBLEM
def test_create_user():
    user = user_service.create("Alice", "alice@example.com")
    assert user is not None  # Passes even if user is broken!

# ✓ FIX
def test_create_user_returns_persisted_entity():
    user = user_service.create("Alice", "alice@example.com")
    assert user.id > 0  # DB-assigned ID proves persistence
    assert user.name == "Alice"
    assert user.email == "alice@example.com"
    assert user.created_at <= datetime.now()
```

### Violation: No Error Tests (Gate 3)

```python
# ❌ PROBLEM
def test_login_success():
    result = auth.login("user@example.com", "password123")
    assert result.token is not None

# ✓ FIX: Add error cases
def test_login_invalid_password():
    result = auth.login("user@example.com", "wrong")
    assert result.status == "error"
    assert result.error_code == "INVALID_CREDENTIALS"

def test_login_user_not_found():
    result = auth.login("nobody@example.com", "password")
    assert result.status == "error"
    assert result.error_code == "USER_NOT_FOUND"

def test_login_empty_password():
    with pytest.raises(ValidationError):
        auth.login("user@example.com", "")
```

### Violation: Test-the-Mock (Gate 1)

```python
# ❌ PROBLEM
def test_send_notification():
    mock_email = Mock()
    service.send_notification(user_id=1, message="Hello")
    mock_email.send.assert_called_once()  # Testing mock behavior!

# ✓ FIX: Assert on observable outcome
def test_send_notification_creates_audit_log():
    service.send_notification(user_id=1, message="Hello")

    # Check observable side effect
    logs = db.query(AuditLog).filter_by(user_id=1).all()
    assert len(logs) == 1
    assert logs[0].action == "notification_sent"
    assert logs[0].message == "Hello"
```

## 3-Phase Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. ARCHITECT: Write ATDD tests (sees quality gates)        │
│    Output: Test suite that defines acceptance criteria     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. IMPLEMENTER: Make tests pass                            │
│    Output: Implementation that passes tests                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. ADVERSARY: Challenge test quality                       │
│    - Check against all 5 quality gates                     │
│    - Write hardening tests for violations                  │
│    Output: Additional tests that expose weak coverage      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2b. IMPLEMENTER: Make hardened tests pass                  │
│     Output: Robust implementation (no stubs/shortcuts)     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ COMPLETION MANIFEST: Prove integration & completeness      │
│     - Parser verifies manifest is filled                   │
│     - All 5 gates must be satisfied                        │
│     Output: Structured proof of done                       │
└─────────────────────────────────────────────────────────────┘
```

## Ralph Loop Integration

```
Iteration 1:
  Input: Task spec + Quality gates + Empty git diff
  Output: Code + tests (may violate gates)
  Manifest check: INCOMPLETE (missing integration)
  → Git commit + respawn

Iteration 2:
  Input: Task spec + Quality gates + Git diff (shows iteration 1 work)
  Agent sees: "Previous iteration violated Gate 2 (no integration)"
  Output: Wires in code + integration tests
  Manifest check: COMPLETE (all gates satisfied)
  → Git commit + done ✓

Key: Each iteration sees FRESH CONTEXT but SAME QUALITY GATES
```

## Manifest Template (Copy-Paste)

```markdown
## Files Created
- [ ] path/to/file.py — Purpose: ...

## Files Modified
- [ ] path/to/existing.py — Reason: ...

## Integration Points
- [ ] Entrypoint: Where new code is called (file:line)
- [ ] Registration: Where new code is registered/wired
- [ ] Configuration: Any config changes needed

## Tests Added
- [ ] Unit tests: N
- [ ] Integration tests: N
- [ ] Edge case/error tests: N
- [ ] Total: N

## Delete Test
- [ ] Deleted files: List new files
- [ ] What breaks: Specific tests/behaviors that would fail

## Known Gaps
- [ ] Gap: Description and reason
(Or: None — all requirements fully met)

## Verification
- [ ] All quality gates satisfied
- [ ] Integration points documented
- [ ] Delete test proves integration
- [ ] Known gaps explicitly listed
```

## Usage in Code

### Automatic (Recommended)

```python
# Templates auto-included via build_static_context()
from src.context.builder import build_static_context

context, size = build_static_context(context_files)
# context now includes:
#   - File contents (if any)
#   - Quality gates (always)
#   - Completion manifest template (always)
```

### Manual

```python
from src.templates import (
    ANTI_PATTERN_SUFFIX,
    COMPLETION_MANIFEST_TEMPLATE,
    format_completion_manifest,
    parse_completion_manifest,
)

# Append to custom prompt
prompt = f"{task}\n{ANTI_PATTERN_SUFFIX}"

# Generate filled manifest
manifest = format_completion_manifest(
    files_created=[("src/feature.py", "New feature")],
    files_modified=[("src/main.py", "Integrated feature")],
    integration_points={'entrypoint': "main.py:42"},
    tests_added={'unit': 5, 'integration': 2, 'edge_case': 3},
    delete_test={
        'deleted_files': ["src/feature.py"],
        'what_breaks': "test_integration.py would fail",
    },
    known_gaps=["Performance optimization deferred"],
)

# Verify it's filled out
parsed = parse_completion_manifest(manifest)
if parsed is None:
    raise ValueError("Unfilled manifest")
```

## Cost & Benefit

**Token Cost:**
- Quality gates: ~467 tokens
- Completion manifest: ~556 tokens
- **Total overhead: ~1,023 tokens per task**

**Time Cost (estimated):**
- Without Tier 0: 20-30 min (multiple retry cycles)
- With Tier 0: 12 min (automated quality enforcement)

**Quality Benefit:**
- Without: Orphan code, shallow tests, hidden gaps
- With: Integrated code, hardened tests, documented gaps

**Scale Benefit:**
- Without: More agents = more broken code
- With: More agents = more working code (ready for Tier 1-2)

## Troubleshooting

### Problem: Agent keeps failing manifest check

**Diagnosis:** Check which gate is violated
```
Parse error: Gate 2 violated
  - No integration point listed
```

**Solution:** Agent needs to show WHERE new code is called
- Add "Files Modified" entry showing integration
- Add "Integration Points" showing exact file:line

### Problem: Adversary finds no violations but code is still shallow

**Diagnosis:** Adversary prompt may not be specific enough

**Solution:** Enhance adversary prompt with specific gate references:
```
"Review against these gates:
 Gate 1: NO test-the-mock - list any mock assertions
 Gate 3: NO happy-path-only - list missing error tests
 Gate 4: NO shallow assertions - list assertions that don't check specifics"
```

### Problem: Manifest looks filled but parser rejects it

**Diagnosis:** No `[x]` checkmarks, just `[ ]` placeholders

**Solution:** Agent must replace `[ ]` with `[x]` and fill actual content
```
❌ - [ ] path/to/file.py — Purpose: ...
✓  - [x] src/services/auth.py — Purpose: User authentication
```

## See Also

- `tier0-backpressure-deep-dive.md` — Full rationale and design
- `tier0-flow-examples.md` — Complete walkthroughs with examples
- `src/templates/README.md` — API documentation
- `src/templates/examples.py` — Runnable code examples

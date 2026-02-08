# Tier 0 Flow Examples: Quality Gates in Action

> Companion to `tier0-backpressure-deep-dive.md` — shows the mechanisms in practice

## Overview

This document demonstrates how the three Tier 0 backpressure mechanisms work together:
1. **Quality Gates** — 5 rules enforced on every task
2. **Adversarial Review** — Challenges test quality automatically
3. **Completion Manifest** — Requires proof before marking "done"

All three integrate seamlessly with the **Ralph Loop** (fresh context per iteration).

---

## The Complete Flow

```
Task: "Add user authentication to API"

┌──────────────────────────────────────────────────────────────────┐
│ RALPH LOOP ITERATION 1                                           │
└──────────────────────────────────────────────────────────────────┘

Spawn Fresh Agent with:
  ✓ Task spec
  ✓ Quality gates (auto-appended via build_static_context)
  ✓ Completion manifest template
  ✓ Git diff (empty - first iteration)

  ┌────────────────────────────────────────────────────────────────┐
  │ Phase 1: Architect (writes ATDD tests)                         │
  └────────────────────────────────────────────────────────────────┘

  Architect sees quality gates and writes tests:
    def test_login_success():
        result = auth_service.login("test@example.com", "secret123")
        assert result.status == "success"
        assert result.token is not None  # ← Shallow assertion

  ┌────────────────────────────────────────────────────────────────┐
  │ Phase 2: Implementer (makes tests pass)                        │
  └────────────────────────────────────────────────────────────────┘

  Implementer creates:
    class AuthService:
        def login(self, email, password):
            # TODO: Actually validate password
            return LoginResult(status="success", token="fake-token")

  Tests: ✓ PASS (but implementation is a stub!)

  ┌────────────────────────────────────────────────────────────────┐
  │ Phase 3: Adversary (challenges quality)                        │
  └────────────────────────────────────────────────────────────────┘

  Adversary reviews against quality gates:

    ✗ GATE 2 VIOLATION: AuthService created but nothing calls it
      Location: src/services/auth_service.py
      Problem: No integration - orphan code

    ✗ GATE 3 VIOLATION: Only success tests, no error tests
      Tests found: test_login_success()
      Missing: invalid password, user not found, etc.

    ✗ GATE 4 VIOLATION: Shallow assertions
      Line: assert result.token is not None
      Problem: Would pass even if token is "fake-token"

  Adversary writes hardening tests:

    def test_login_returns_valid_jwt():
        """Gate 4: Assert on specific token structure"""
        result = auth_service.login("test@example.com", "secret123")
        decoded = jwt.decode(result.token, SECRET_KEY)
        assert decoded["user_id"] == user.id
        assert decoded["exp"] > time.time()

    def test_login_invalid_password():
        """Gate 3: Error path coverage"""
        result = auth_service.login("test@example.com", "wrong")
        assert result.status == "error"
        assert result.error_code == "INVALID_CREDENTIALS"
        assert result.token is None

    def test_login_user_not_found():
        """Gate 3: Error path coverage"""
        result = auth_service.login("nobody@example.com", "secret")
        assert result.status == "error"
        assert result.error_code == "USER_NOT_FOUND"

  ┌────────────────────────────────────────────────────────────────┐
  │ Phase 2b: Implementer (makes hardened tests pass)              │
  └────────────────────────────────────────────────────────────────┘

  Implementer improves implementation:
    class AuthService:
        def login(self, email, password):
            user = db.get_user_by_email(email)
            if not user:
                return LoginResult(
                    status="error",
                    error_code="USER_NOT_FOUND"
                )

            if not bcrypt.check_password(password, user.password_hash):
                return LoginResult(
                    status="error",
                    error_code="INVALID_CREDENTIALS"
                )

            token = jwt.encode({
                "user_id": user.id,
                "exp": time.time() + 3600
            }, SECRET_KEY)

            return LoginResult(status="success", token=token)

  Tests: ✓ ALL PASS (including adversary-hardened tests)

  ┌────────────────────────────────────────────────────────────────┐
  │ Completion Manifest Check                                       │
  └────────────────────────────────────────────────────────────────┘

  Agent produces manifest:

    ## Files Created
    - [x] src/services/auth_service.py
    - [x] tests/test_auth_service.py

    ## Files Modified
    [EMPTY] ← PROBLEM!

    ## Integration Points
    [EMPTY] ← GATE 2 VIOLATION

    ## Tests Added
    - [x] Unit: 5
    - [x] Total: 5

  Parse result: ✗ INCOMPLETE
    Reason: Gate 2 violated (no integration), Gate 5 violated (no wiring proof)

End of Iteration 1: GIT COMMIT (code + tests, but not integrated)

┌──────────────────────────────────────────────────────────────────┐
│ RALPH LOOP ITERATION 2 (Fresh Agent Spawn)                       │
└──────────────────────────────────────────────────────────────────┘

Spawn Fresh Agent with:
  ✓ Task spec (same)
  ✓ Quality gates (same - fresh context)
  ✓ Completion manifest template
  ✓ Git diff (shows AuthService exists but not called)

Agent sees git diff:
  + src/services/auth_service.py (AuthService.login() method)
  + tests/test_auth_service.py (5 tests)

Agent recognizes from quality gates:
  "Previous iteration created AuthService but:
   - Gate 2 requires: NO orphan code (must be called)
   - Gate 5 requires: WIRING PROOF (show integration point)"

  ┌────────────────────────────────────────────────────────────────┐
  │ Phase 1: Architect (adds integration tests)                    │
  └────────────────────────────────────────────────────────────────┘

  Architect adds API integration tests:

    def test_login_endpoint():
        """Integration test for POST /login"""
        response = client.post("/login", json={
            "email": "test@example.com",
            "password": "secret123"
        })
        assert response.status_code == 200
        assert "token" in response.json()

        # Gate 4: Specific assertion
        token = response.json()["token"]
        decoded = jwt.decode(token, SECRET_KEY)
        assert decoded["user_id"] > 0

  ┌────────────────────────────────────────────────────────────────┐
  │ Phase 2: Implementer (wires in AuthService)                    │
  └────────────────────────────────────────────────────────────────┘

  Implementer modifies:

    # src/api/routes.py
    from src.services.auth_service import AuthService

    @app.post("/login")
    def login(request: LoginRequest):
        auth_service = container.resolve(AuthService)  # Gate 2: Integration
        result = auth_service.login(request.email, request.password)

        if result.status == "error":
            raise HTTPException(status_code=401, detail=result.error_code)

        return {"token": result.token}

    # src/di/container.py
    container.register(AuthService)  # Gate 5: Wiring proof

  Tests: ✓ ALL PASS (unit + integration)

  ┌────────────────────────────────────────────────────────────────┐
  │ Phase 3: Adversary (reviews integration)                       │
  └────────────────────────────────────────────────────────────────┘

  Adversary checks gates:
    ✓ Gate 1: Not asserting on mocks (checking actual HTTP responses)
    ✓ Gate 2: Integration proven (routes.py calls AuthService)
    ✓ Gate 3: Error tests present (invalid password, user not found)
    ✓ Gate 4: Specific assertions (checking JWT structure, user_id)
    ✓ Gate 5: Wiring documented (see manifest below)

  No violations found!

  ┌────────────────────────────────────────────────────────────────┐
  │ Completion Manifest Check                                       │
  └────────────────────────────────────────────────────────────────┘

  Agent produces manifest:

    ## Files Created
    - [x] src/services/auth_service.py — User authentication service
    - [x] tests/test_auth_service.py — Unit tests for AuthService
    - [x] tests/test_auth_api.py — Integration tests for /login endpoint

    ## Files Modified
    - [x] src/api/routes.py — Added POST /login endpoint at line 67
    - [x] src/di/container.py — Registered AuthService at line 23
    - [x] requirements.txt — Added PyJWT, bcrypt dependencies

    ## Integration Points
    - [x] Entrypoint: routes.py:67 calls auth_service.login()
    - [x] Registration: container.py:23 registers AuthService
    - [x] Configuration: DB connection already configured

    ## Tests Added
    - [x] Unit: 6 (login success, invalid password, user not found,
                    expired token, malformed input, SQL injection)
    - [x] Integration: 4 (POST /login success/error, POST /register,
                          authenticated endpoint access)
    - [x] Edge case: 3 (empty password, special characters, timeout)
    - [x] Total: 13

    ## Delete Test
    - [x] Deleted files: src/services/auth_service.py
    - [x] What breaks: test_auth_api.py::test_login_endpoint fails with
                       ImportError, POST /login returns 500 (service not found)

    ## Known Gaps
    - [ ] Rate limiting on login attempts deferred to security sprint
    - [ ] OAuth integration planned for Q2
    - [ ] MFA support not in scope for MVP

  Parse result: ✓ COMPLETE
    - All gates satisfied
    - Integration proven with specific locations
    - Manifest filled with detailed information
    - Known gaps explicitly listed

End of Iteration 2: GIT COMMIT (fully integrated)

┌──────────────────────────────────────────────────────────────────┐
│ RALPH LOOP: TASK COMPLETE ✓                                      │
└──────────────────────────────────────────────────────────────────┘

Git history:
  Commit 1: "Add AuthService with hardened tests (not integrated)"
  Commit 2: "Integrate AuthService into API routes with API tests"

Final result:
  ✓ Working implementation (not stubs)
  ✓ Hardened tests (adversary-challenged)
  ✓ Fully integrated (routes → service → DB)
  ✓ Proven complete (manifest shows all work)
  ✓ Known gaps documented (not hidden)
```

---

## Key Synergies

### Ralph Loop + Quality Gates

**Ralph Loop provides:**
- Fresh context each iteration (no degradation)
- Progress tracked via git commits (artifacts > memory)
- Brute-force persistence (keeps trying until done)

**Quality Gates provide:**
- Definition of "done" (what must be satisfied)
- Standards enforced on EVERY iteration
- Can't be forgotten across spawns

**Together:** Agent sees the same quality requirements every time it spawns, preventing "requirement drift"

### Adversarial Review + Quality Gates

**Adversarial Review provides:**
- Automated mutation testing
- Challenges test quality
- Writes hardening tests

**Quality Gates provide:**
- Specific criteria for review (the 5 gates)
- Clear examples of violations
- Framework for adversary prompt

**Together:** Adversary knows exactly what to look for (gates) and how to challenge it (hardening tests)

### Completion Manifest + All Mechanisms

**Completion Manifest provides:**
- Proof of integration required
- Structured format (can't skip sections)
- Parser detects unfilled templates

**Quality Gates provide:**
- What to verify in manifest (integration, wiring)
- Standards for "Files Modified" section

**Adversarial Review provides:**
- Verification that tests in manifest are real
- Challenge "Tests Added" counts

**Ralph Loop provides:**
- Context for git diff analysis
- "Delete test" can reference actual commits

**Together:** Manifest becomes a verified artifact, not just agent self-reporting

---

## Before & After Comparison

### ❌ Without Tier 0 Mechanisms

```
You: "Add user authentication"

Agent (5 min):
  + src/services/auth_service.py
  + test_login_success()
  "Done!"

You (review):
  ✗ AuthService not called anywhere (orphan code)
  ✗ Only happy-path test
  ✗ Test asserts on mock, not behavior
  ✗ No mention of password hashing
  "Try again"

Agent (5 min):
  "Fixed!"

You (review):
  ✗ Still not integrated into routes
  ✗ Still missing error tests
  "Try again"

Agent (5 min):
  "Now it's done!"

You (review):
  ✗ Integrated but broke existing tests
  ✗ No consideration of DI registration
  "Try again"

Total: 20-30 minutes + frustration + technical debt
```

### ✓ With Tier 0 Mechanisms

```
You: "Add user authentication"

Ralph Loop Iteration 1 (8 min):
  Phase 1: Architect writes tests (sees quality gates)
  Phase 2: Implementer makes tests pass
  Phase 3: Adversary hardens tests (finds Gate 2,3,4 violations)
  Phase 2b: Implementer makes hardened tests pass
  Manifest: ✗ INCOMPLETE (no integration)
  Commit: "Add AuthService with tests (not integrated)"

Ralph Loop Iteration 2 (4 min):
  Fresh agent sees: AuthService exists, gates require integration
  Phase 1: Architect adds integration tests
  Phase 2: Implementer wires into routes + DI
  Phase 3: Adversary reviews: ✓ All gates satisfied
  Manifest: ✓ COMPLETE with proof
  Commit: "Integrate AuthService into API routes"

You (review):
  Read manifest:
    ✓ Integration proven (routes.py:67, container.py:23)
    ✓ 13 tests (breakdown by type shows coverage)
    ✓ Delete test proves integration
    ✓ Known gaps explicitly listed
  "Merge!"

Total: 12 minutes + confidence + production-ready code
```

---

## Real-World Scenario: Caught by Quality Gates

### Gate 1: NO test-the-mock

**Violation:**
```python
def test_send_email():
    mock_client = Mock()
    email_service.send("test@example.com", "Hello")
    mock_client.send.assert_called_once()  # ❌ Testing the mock
```

**Adversary catches:**
```python
def test_send_email_returns_message_id():
    """Gate 1: Assert on observable behavior"""
    result = email_service.send("test@example.com", "Hello")
    assert result.message_id.startswith("msg_")
    assert result.status == "sent"
```

### Gate 2: NO orphan code

**Violation:**
```
Files Created:
  + src/services/payment_processor.py

Files Modified:
  [none]  # ❌ Nothing calls it
```

**Manifest catches:**
```
Parse error: Gate 2 violated
  - PaymentProcessor created but no integration point listed
  - Must show where it's called from application entrypoint
```

### Gate 3: NO happy-path-only

**Violation:**
```python
# Only success test
def test_create_order_success():
    order = order_service.create(user_id=1, items=[...])
    assert order.id > 0
```

**Adversary adds:**
```python
def test_create_order_empty_cart():
    """Gate 3: Edge case"""
    with pytest.raises(ValidationError):
        order_service.create(user_id=1, items=[])

def test_create_order_insufficient_inventory():
    """Gate 3: Error path"""
    result = order_service.create(user_id=1, items=[out_of_stock_item])
    assert result.status == "error"
    assert result.error_code == "INSUFFICIENT_INVENTORY"
```

### Gate 4: NO shallow assertions

**Violation:**
```python
def test_get_user():
    user = user_service.get(123)
    assert user is not None  # ❌ Shallow
```

**Adversary hardens:**
```python
def test_get_user_returns_complete_profile():
    """Gate 4: Assert on specific values"""
    user = user_service.get(123)
    assert user.id == 123
    assert user.email == "test@example.com"
    assert user.created_at < datetime.now()
    assert len(user.roles) > 0
```

### Gate 5: WIRING PROOF

**Violation:**
```
Files Modified:
  - src/api/routes.py  # ❌ No explanation WHY
```

**Manifest requires:**
```
Files Modified:
  - [x] src/api/routes.py — Added POST /checkout endpoint at line 89,
                            imported PaymentProcessor, called process_payment()
  - [x] src/di/container.py — Registered PaymentProcessor as singleton
  - [x] config/settings.py — Added STRIPE_API_KEY configuration
```

---

## Integration with Existing Codebase

### Automatic via `build_static_context()`

```python
# src/context/builder.py
from src.templates import ANTI_PATTERN_SUFFIX, COMPLETION_MANIFEST_TEMPLATE

def build_static_context(context_files):
    """Quality gates and manifest automatically appended."""
    static_parts = []

    # Load context files
    if context_files:
        file_context = build_context(context_files)
        if file_context:
            static_parts.append(file_context)

    # ALWAYS include quality gates and manifest
    static_parts.append(ANTI_PATTERN_SUFFIX)
    static_parts.append("\n")
    static_parts.append(COMPLETION_MANIFEST_TEMPLATE)

    return ''.join(static_parts), len(static_parts)
```

Every agent spawn via supervisor.py automatically gets:
1. Context files (if specified)
2. Quality gates (always)
3. Completion manifest template (always)

### Manual Usage

```python
from src.templates import format_completion_manifest, parse_completion_manifest

# Agent fills out manifest
manifest_text = format_completion_manifest(
    files_created=[("src/feature.py", "New feature")],
    files_modified=[("src/main.py", "Integrated feature")],
    integration_points={'entrypoint': "main.py:42"},
    tests_added={'unit': 5, 'integration': 2, 'edge_case': 3},
    delete_test={
        'deleted_files': ["src/feature.py"],
        'what_breaks': "test_integration.py would fail"
    },
)

# Verify it's actually filled out
parsed = parse_completion_manifest(manifest_text)
if parsed is None:
    raise ValueError("Agent submitted unfilled manifest")

print(f"Tests added: {parsed['total_tests']}")
print(f"Files created: {parsed['files_created_count']}")
```

---

## Next Steps (Tier 0 Completion)

This flow requires completing the remaining Tier 0 tasks:

1. **agent-orchestrator-wc1** (P1): Integration entrypoint verification gate
   - Automated check: trace call path from entrypoint to new code
   - "Delete test" automation

2. **agent-orchestrator-67o** (P1): 3-phase execution (adversarial review)
   - Implement architect → implementer → adversary flow
   - Adversary prompt that references quality gates

3. **agent-orchestrator-6mv** (P2): Multi-repo integration verification
   - Contract-first decomposition
   - Consumer test gates

Once Tier 0 is complete, it unblocks **Tier 1: Task Decomposition Mastery**.

---

## References

- `tier0-backpressure-deep-dive.md` — Rationale and mechanism design
- `src/templates/README.md` — Templates API documentation
- `src/templates/examples.py` — Runnable code examples
- [Geoffrey Huntley - Ralph Loop](https://ghuntley.com/loop/)
- [Steve Yegge - Gas Town](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04)

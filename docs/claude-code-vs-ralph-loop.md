# Claude Code REPL vs Ralph Loop: When to Use Which

## TL;DR

**Claude Code REPL:** Best for interactive development where you want control at each step
**Ralph Loop Orchestrator:** Best for unattended execution where you want automated quality enforcement

Both can implement quality gates. The key difference is **human-in-the-loop vs automated iteration**.

---

## Side-by-Side Comparison

| Aspect | Claude Code REPL | Ralph Loop Orchestrator |
|--------|------------------|-------------------------|
| **Execution Model** | Interactive REPL, human reviews each step | Automated loop, spawns fresh agents until done |
| **Context Management** | Continuous conversation in one session | Fresh context per iteration (no memory bleed) |
| **Backpressure Mechanism** | Human rejection: "Try again" | Programmatic gates: manifest parser rejects incomplete work |
| **Quality Gates** | Via CLAUDE.md or skills (human enforces) | Via templates in static context (automatic enforcement) |
| **Human Involvement** | High - review every change | Low - review only final manifest |
| **Iteration Speed** | Fast (no context rebuild) | Slower (fresh spawn per iteration) |
| **Token Efficiency** | Efficient (reuses context) | Higher cost (rebuilds context each spawn) |
| **Suitable For** | Exploratory work, debugging, complex reasoning | Known task patterns, ATDD workflows, unattended execution |
| **Failure Mode** | User fatigue ("just accept it") | Continues until gates satisfied or budget exhausted |
| **Scalability** | 1 human : 1 agent | 1 human : N agents (parallel orchestration) |

---

## Scenario 1: Interactive Development (Claude Code Wins)

### Task: "Debug why the login endpoint returns 500"

**Claude Code REPL Flow:**
```
You: Debug the login endpoint 500 error

Claude: Let me check the error logs...
[reads logs, identifies issue]
Claude: Found it - NullReferenceException in AuthService line 42

You: Fix it

Claude: [applies fix, shows diff]

You: Looks good, commit it

Claude: [creates commit]

Done in 3 minutes, highly interactive
```

**Ralph Loop Flow:**
```
You: Debug the login endpoint 500 error

Iteration 1:
  Agent: Reads logs, identifies issue, applies fix
  Manifest check: "Where's the test that prevents regression?"
  ✗ Incomplete (Gate 3 violation - no regression test)

Iteration 2:
  Agent: Re-analyzes, adds fix + regression test
  Manifest check: ✓ Complete

Done in 8 minutes (fresh context overhead)
```

**Winner: Claude Code** — Interactive debugging doesn't need automated iteration. The back-and-forth is the value.

---

## Scenario 2: Unattended ATDD Task (Ralph Loop Wins)

### Task: "Add user registration with email verification"

**Claude Code REPL Flow:**
```
You: Add user registration with email verification

Claude: [creates UserService.register() method]

You: Does this send verification emails?

Claude: Not yet, let me add that
[adds EmailService integration]

You: What about duplicate email handling?

Claude: Good catch, adding that
[adds duplicate check]

You: Are there tests?

Claude: Let me add tests
[adds test_register_success()]

You: What about error cases?

Claude: Adding those
[adds test_duplicate_email()]

You: Is this wired into the API?

Claude: Not yet, let me do that
[adds /register endpoint]

... 10+ back-and-forth exchanges over 30 minutes
```

**Ralph Loop Flow:**
```
You: Add user registration with email verification

Iteration 1:
  Architect: Writes ATDD tests (success, duplicate, invalid email)
  Implementer: Creates UserService.register(), EmailService integration
  Adversary: "Where's the API integration?" (Gate 2 violation)
  Manifest: ✗ Incomplete (no integration)

Iteration 2:
  Agent sees Gate 2 violation in previous git diff
  Adds /register endpoint, wires into routes
  Manifest: ✓ Complete (all gates satisfied)

You review manifest, merge

Done in 12 minutes unattended
```

**Winner: Ralph Loop** — You didn't have to ask 10 questions. Quality gates enforced automatically.

---

## Scenario 3: Using Claude Code with Skills for Backpressure

You can implement quality gates in Claude Code using CLAUDE.md or custom skills:

### CLAUDE.md Approach

```markdown
# CLAUDE.md

## Quality Gates - Do NOT mark work complete until:

1. NO test-the-mock: Assert on observable behavior
2. NO orphan code: Every new type must be called from existing code
3. NO happy-path-only: Every success test needs error tests
4. NO shallow assertions: Assert on specific values
5. WIRING PROOF: List every file modified and why
```

**How it works:**
- Claude Code reads CLAUDE.md automatically
- You reinforce: "Check the quality gates"
- Claude self-reviews against gates
- **You still review and accept each step**

**Difference from Ralph Loop:**
- **Human enforcement:** You must remember to ask "did you check the gates?"
- **Continuous context:** Claude can "forget" gates as conversation grows
- **No automated rejection:** If Claude says "done", you must notice it's incomplete

### Skill Approach

Create `/verify-gates` skill:

```python
# .claude/skills/verify-gates.py
def verify_gates(changes):
    """Check if changes satisfy all 5 quality gates."""
    violations = []

    # Check Gate 2: Orphan code
    new_classes = find_new_classes(changes)
    for cls in new_classes:
        if not has_callers(cls):
            violations.append(f"Gate 2: {cls} has no callers (orphan code)")

    # Check Gate 3: Happy-path-only
    new_tests = find_new_tests(changes)
    if not has_error_tests(new_tests):
        violations.append("Gate 3: Only success tests found, no error cases")

    return violations
```

**How it works:**
- You call `/verify-gates` after Claude finishes
- Skill programmatically checks violations
- **You still decide whether to proceed or ask for fixes**

**Difference from Ralph Loop:**
- **Human decision:** Skill reports violations, you decide action
- **One-shot:** No automatic re-iteration until gates pass
- **In-session:** Works within continuous conversation

---

## The Key Philosophical Difference

### Claude Code REPL Philosophy
**"Human is the orchestrator, Claude is the tool"**

- You break down tasks
- You review each step
- You decide when it's done
- Your backpressure: "Try again"

**Strengths:**
- High control
- Fast iteration for exploratory work
- Natural for debugging/investigation

**Weaknesses:**
- Requires constant attention
- You might miss quality issues due to fatigue
- Doesn't scale to multiple parallel agents

### Ralph Loop Philosophy
**"Code the orchestration, automate the backpressure"**

- Quality gates break down the definition of "done"
- Fresh context prevents degradation
- Automated iteration until programmatic verification passes
- Your backpressure: Parse manifest, reject if incomplete

**Strengths:**
- Can run unattended
- Doesn't forget quality standards
- Scales to parallel multi-agent (Tier 2)

**Weaknesses:**
- Slower for simple tasks (fresh context overhead)
- Less flexible for exploratory work
- Requires upfront task specification

---

## When to Use Each

### Use Claude Code REPL When:

✅ **Exploring unfamiliar code**
   - "How does authentication work here?"
   - Interactive Q&A is faster than fresh context per question

✅ **Debugging production issues**
   - "Why is this failing in prod but not locally?"
   - Need back-and-forth to narrow down root cause

✅ **Prototyping/spiking**
   - "Can we use library X for feature Y?"
   - Exploratory, many pivots expected

✅ **Learning a new codebase**
   - "Walk me through the payment flow"
   - Conversational context builds understanding

✅ **Complex architectural decisions**
   - "Should we use event sourcing here?"
   - Requires human judgment at each step

### Use Ralph Loop Orchestrator When:

✅ **Well-defined ATDD tasks**
   - "Add password reset feature per spec.md"
   - Clear acceptance criteria, just need reliable execution

✅ **Repetitive patterns**
   - "Add CRUD endpoints for Product model"
   - Known pattern, automate quality enforcement

✅ **Unattended execution**
   - "Implement these 5 features overnight"
   - Can't babysit, need automated iteration

✅ **Multi-agent parallelization** (Tier 2)
   - "Agents 1-3: work on different modules simultaneously"
   - Human can't orchestrate 3 agents manually

✅ **Known quality pitfalls**
   - "Previous agents kept creating orphan code"
   - Codify the backpressure so it's always enforced

---

## Hybrid Approach: Best of Both Worlds

### Workflow 1: Claude Code → Ralph Loop

**Interactive design, automated execution:**

```
1. Use Claude Code REPL to:
   - Explore the codebase
   - Design the approach
   - Create ATDD spec (spec.md)

2. Hand off to Ralph Loop:
   - Load spec.md as task
   - Ralph Loop executes with quality gates
   - Iterates until manifest passes

3. Review manifest in Claude Code:
   - Check integration points
   - Verify known gaps are acceptable
   - Merge or iterate
```

**Example:**
```
You (in Claude Code): "Help me design a password reset flow"
Claude: [interactive discussion, explores options]
You: "Write this as an ATDD spec"
Claude: [creates spec.md with acceptance criteria]

You (in terminal): "./ralph_loop.py --spec spec.md"
Ralph Loop: [executes unattended, enforces quality gates]
  Iteration 1: Creates service (no integration) → ✗
  Iteration 2: Integrates + tests → ✓

You (in Claude Code): "Review this manifest"
Claude: [reviews, finds integration proven, merge]
```

### Workflow 2: Ralph Loop with Claude Code Fallback

**Automated first, human rescue:**

```
1. Ralph Loop attempts task
   - If succeeds: Done
   - If fails after N iterations: Escalate to human

2. Human uses Claude Code to debug:
   - "Why did the loop get stuck?"
   - Fix blocker, create smaller task

3. Ralph Loop retries with refined spec
```

---

## Implementing Quality Gates in Claude Code

If you want Ralph-style backpressure in Claude Code without the orchestrator:

### Option 1: CLAUDE.md with Checklist

```markdown
# CLAUDE.md

Before marking ANY task complete, produce this checklist:

## Quality Verification Checklist

- [ ] **Gate 1 (NO test-the-mock):** All assertions check observable behavior, not mock calls
- [ ] **Gate 2 (NO orphan code):** Every new public class/method is called from existing code. Integration point: _____
- [ ] **Gate 3 (NO happy-path-only):** For every success test, there's a corresponding error/edge test
- [ ] **Gate 4 (NO shallow assertions):** All assertions check specific values, not just null checks
- [ ] **Gate 5 (WIRING PROOF):** Listed all modified files with reasons

## Integration Proof

Entrypoint: _____
Modified files: _____
Tests added: Unit: ___ Integration: ___ Edge: ___

If any gate fails, DO NOT mark complete. Fix first.
```

**Usage:**
```
You: Add user login feature

Claude: [implements feature]
       [produces checklist]
       ✗ Gate 2 failed: UserService not called from anywhere
       Let me fix that...
       [adds integration]
       ✓ All gates satisfied

You: Looks good, commit
```

**Pros:** Simple, no infrastructure needed
**Cons:** Claude might "cheat" checklist (self-grading issue), you still review

### Option 2: /verify Skill (Programmatic Check)

```bash
# .claude/skills/verify
#!/bin/bash
# Programmatically verify quality gates

echo "Checking quality gates..."

# Gate 2: Check for orphan code
new_classes=$(git diff HEAD --name-only | xargs grep -l "^class " | ...)
for class in $new_classes; do
  if ! grep -r "import.*$class" --exclude-dir=tests; then
    echo "❌ Gate 2 violation: $class has no imports (orphan code)"
    exit 1
  fi
done

# Gate 3: Check for error tests
if ! git diff HEAD tests/ | grep -q "test.*error\|test.*invalid"; then
  echo "❌ Gate 3 violation: No error tests found"
  exit 1
fi

echo "✅ All gates passed"
```

**Usage:**
```
You: Add user login feature

Claude: [implements feature]

You: /verify

Skill: ✅ All gates passed

You: Commit it
```

**Pros:** Automated verification, catches violations programmatically
**Cons:** Still requires you to remember to call `/verify`, no auto-iteration

### Option 3: Pre-Commit Hook (Hybrid)

```bash
# .git/hooks/pre-commit
#!/bin/bash
# Enforce quality gates on every commit

python3 << 'EOF'
from src.templates.completion_manifest import parse_completion_manifest

# Check if commit message includes manifest
manifest = get_commit_message()

parsed = parse_completion_manifest(manifest)
if parsed is None:
    print("❌ Commit rejected: No valid completion manifest")
    print("Include manifest in commit message or use --no-verify")
    exit(1)

if parsed['total_tests'] < 3:
    print("❌ Commit rejected: Insufficient tests (minimum 3)")
    exit(1)

print("✅ Quality gates satisfied")
EOF
```

**Usage:**
```
You: Add user login

Claude: [implements]

You: Commit this

Git hook: ❌ Rejected (no completion manifest)

You: Claude, add a completion manifest to the commit message

Claude: [produces manifest]

You: Commit

Git hook: ✅ Passed

Commit succeeds
```

**Pros:** Enforced automatically, can't bypass without --no-verify
**Cons:** Blocks commits, might slow down rapid iteration

---

## The Evolution Path

### Stage 5-6 (Current - Most Users)
**Claude Code REPL with skills**
- Human orchestrates
- Skills add automation
- CLAUDE.md provides guidelines

### Stage 6+ (Tier 0 Goal)
**Ralph Loop with Quality Gates**
- Automated iteration
- Programmatic verification
- Human reviews manifest

### Stage 7 (Tier 1-2 Goal)
**Multi-Agent with Orchestrator**
- Decompose tasks
- Parallel agents
- Contract-based integration
- Human reviews integration tests

### Stage 8 (Tier 3 Goal)
**Fully Automated Orchestrator**
- Auto-decomposition
- Self-healing
- Human monitors dashboard

**Claude Code remains valuable at ALL stages** for:
- Debugging orchestrator issues
- Exploratory work
- Complex architectural decisions
- Learning and investigation

---

## Conclusion

**Ralph Loop ≠ Replacement for Claude Code**
**Ralph Loop = Complementary tool for specific workflows**

| Use Case | Best Tool |
|----------|-----------|
| Debugging, exploring, learning | Claude Code REPL |
| Well-defined ATDD tasks | Ralph Loop |
| Prototyping, architectural design | Claude Code REPL |
| Unattended execution | Ralph Loop |
| Interactive problem-solving | Claude Code REPL |
| Repetitive patterns with quality pitfalls | Ralph Loop |
| Quick one-off changes | Claude Code REPL |
| Multi-agent parallelization | Ralph Loop (Tier 2+) |

**Recommended workflow:**
1. Use Claude Code to explore, design, create specs
2. Use Ralph Loop to execute ATDD tasks unattended
3. Use Claude Code to review manifests and debug failures
4. Use git hooks + skills for quality gates in interactive mode

**The meta-insight:** You're coding the orchestration pattern so you can scale beyond 1:1 human-agent ratio. Claude Code is perfect for 1:1. Ralph Loop targets 1:N.

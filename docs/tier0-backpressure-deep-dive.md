# Tier 0: Backpressure Mechanisms for the Ralph Loop

> Prerequisite to scaling from Stage 6 → 7+ in Yegge's Developer Evolution Model.
> If your single-agent loop leaks incomplete work, scaling to more agents multiplies the leak.

## Problem Statement

Three distinct failure modes observed in daily agent-assisted development:

1. **Shallow/useless tests**: Tests that pass with stubs, assert on mocks, or verify framework behavior rather than business logic
2. **Missing integration**: Code works in isolation but isn't wired into the system — nothing calls it
3. **Hard-to-spot incompleteness**: Agent says "done", tests pass, but 20% of the work is missing

## Mechanism 1: Adversarial Review Phase

**Problem it solves**: Agent writes tests that look right but don't constrain the implementation meaningfully.

**How it works**: After the implement phase produces green tests, a separate agent (or separate prompt) gets this instruction:

> You are a code reviewer whose job is to find false confidence. Given these tests and this implementation:
> 1. List every test that would still pass if the implementation returned a hardcoded value or no-op
> 2. List every test that asserts on a mock rather than on observable behavior
> 3. List every public method/endpoint with no test coverage
> 4. List every error path that isn't tested
> 5. For each issue found, write the missing/corrected test

**Key insight**: The adversary doesn't fix the code — it writes better tests. Then the loop continues: the implementation agent must make the new tests pass. This is automated mutation testing via adversarial prompting.

**Cost/benefit**: Adds ~30-50% more tokens per task. But catches agents declaring "done" on shallow coverage. At scale, the cost of shipping broken code and debugging it later dwarfs the review cost.

**Adaptation for .NET**: Same pattern. Adversary prompt: "Review these xUnit/NUnit tests. Which ones would pass even if the implementation were replaced with `throw new NotImplementedException()`?"

## Mechanism 2: Integration Entrypoint Verification

**Problem it solves**: Code exists, tests pass, but nothing calls it. Feature is "done" but unreachable.

### Check A: Static Reachability Analysis

After the agent finishes, ask it (or a verifier agent):

> Trace the call path from the application's entrypoint (Main, Startup, API controller, event handler) to the new code. List every hop. If you cannot trace a complete path, the feature is not integrated.

For .NET: Is there a controller action, middleware registration, DI binding, message handler, or startup hook that reaches the new code?

### Check B: The "Delete Test"

> If I deleted all the new files you created, what existing behavior would break?

If the answer is "nothing" — the code isn't integrated. Truly integrated code has tendrils into the existing system; removing it should break something.

### Encoding as a Gate

Add to ATDD acceptance criteria template:

```
Acceptance criteria:
- [ ] Feature works through [specific entrypoint]
- [ ] Removing new code causes [specific existing test] to fail
- [ ] New code is registered/wired in [specific location]
```

The third checkbox forces the agent to name the integration point before the task can be considered done.

## Mechanism 3: Anti-Pattern Prompt Suffix

**Problem it solves**: Agents repeat the same mistakes because they don't know your standards.

**How it works**: A short, project-specific list appended to every task prompt. Constraints on *how* to build, not *what* to build.

```
QUALITY GATES — Do not mark this task complete until ALL are satisfied:

1. NO test-the-mock: Every assertion must verify observable behavior,
   not mock interactions. If you mock a dependency, assert on the
   output/side-effect, not on whether the mock was called.

2. NO orphan code: Every new public type/method must be called from
   existing code. Show the integration point.

3. NO happy-path-only: For every success test, write at least one
   failure/edge test. Common misses: null input, empty collection,
   duplicate entry, network failure, timeout.

4. NO shallow assertions: "Assert.NotNull" alone is never sufficient.
   Assert on specific values, counts, or state changes.

5. WIRING PROOF: List every existing file you modified and why. If
   you only created new files, explain how they're reachable from
   the application entrypoint.
```

Cost: ~150 tokens of context. Directly addresses all three failure modes.

## Mechanism 4: Completion Manifest

**Problem it solves**: "Hard to spot" incompleteness.

**How it works**: Before marking a task complete, the agent must produce:

```
## Completion Manifest
### Files created: [list]
### Files modified: [list with reason]
### Integration points: [where new code connects to existing]
### Tests added: [count, with breakdown by type]
  - Unit: X
  - Integration: Y
  - Edge case/error: Z
### Known gaps: [anything not covered, and why]
### Delete test: "If you deleted [files], [these tests] would fail"
```

The "known gaps" field is critical. Agents will often *know* something is incomplete but won't volunteer it unless asked. An empty "known gaps" from an agent is itself a signal to scrutinize more carefully.

## Combined Flow

```
Task prompt + Anti-pattern suffix
        │
        ▼
  Architect (writes ATDD tests including integration tests)
        │
        ▼
  Implementer (makes tests pass)
        │
        ▼
  Adversary (challenges test quality, writes hardening tests)
        │
        ▼
  Implementer again (makes hardened tests pass)
        │
        ▼
  Completion manifest (agent proves integration + coverage)
        │
        ▼
  Entrypoint verification (automated or reviewer checks reachability)
        │
        ▼
  Done ✓
```

## Multi-Repo Integration Verification

### The Unique Challenge

In multi-repo environments (especially .NET with shared code monorepos), integration verification is harder because:

1. **Cross-repo contracts are implicit**: Service A calls Service B's API, but the contract lives in neither repo cleanly
2. **Shared library changes ripple**: A change in the monorepo shared lib can break N consumers
3. **Agent scope is per-repo**: An agent working in Repo A doesn't see Repo B's code

### Strategies

#### Strategy 1: Contract-First Decomposition
Before any agent starts coding, define the cross-repo contract explicitly:
- API contracts (OpenAPI/Swagger specs, proto files, shared DTOs)
- Event contracts (message schemas, topic names)
- Shared library interfaces (what's public, what's the expected behavior)

The contract becomes the acceptance test. Each repo's agent implements their side of the contract independently.

#### Strategy 2: The "Consumer Test" Gate
For shared library changes: before merging, require that the agent (or a second agent in the consuming repo) runs the consumer's test suite against the new version. If the shared lib change is backward-compatible, consumers pass without changes. If not, the task isn't done — it must include consumer updates.

#### Strategy 3: Integration Environment as Oracle
Maintain a staging/integration environment where all repos are deployed together. The final verification gate is: deploy everything and run integration tests. This is the "delete test" at the system level — if the feature doesn't work end-to-end in staging, it's not done.

#### Strategy 4: Dependency-Aware Task Scoping
When creating tasks that span repos, explicitly list:
- Which repos need changes
- What the dependency order is (shared lib first, then consumers)
- What the cross-repo acceptance test looks like

Encode this in beads as dependent issues: "Shared lib change" blocks "Service A update" blocks "Integration test".

### Anti-Pattern: Agent Per Repo Without Coordination
The failure mode is: Agent 1 changes the shared lib API, Agent 2 (in a different repo) is still coding against the old API. By the time Agent 2 finishes, its code is already broken.

**Fix**: Shared lib changes must complete and be published before consumer agents start. This is sequential by necessity — don't try to parallelize across a breaking change boundary.

---

## Advancement Context

This document is part of the progression through Yegge's 8 Stages of Developer Evolution:

| Priority | Tier | Focus |
|----------|------|-------|
| **Now** | 0 | Backpressure & verification (this document) |
| Next | 1 | Task decomposition — breaking work into parallel-safe units |
| Then | 2 | Coordination — multi-agent conflict resolution |
| Later | 3 | Orchestrator automation — automate what you've mastered manually |

### References
- [Steve Yegge - Welcome to Gas Town](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04)
- [Geoffrey Huntley - Everything is a Ralph Loop](https://ghuntley.com/loop/)
- [Yegge's Developer-Agent Evolution Model](https://justin.abrah.ms/blog/2026-01-08-yegge-s-developer-agent-evolution-model.html)

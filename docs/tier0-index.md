# Tier 0 Documentation Index

## Overview

Tier 0 implements backpressure mechanisms to ensure single-agent reliability before scaling to multi-agent coordination. The three core mechanisms are:

1. **Quality Gates** — 5 rules enforced on every task
2. **Completion Manifest** — Structured proof required before "done"
3. **Adversarial Review** — Automated test quality challenge

## Documentation Map

### Start Here

- **[tier0-quick-reference.md](tier0-quick-reference.md)** ⭐
  - One-page cheat sheet
  - The 5 quality gates with examples
  - Completion manifest template
  - Common violations and fixes
  - Usage patterns

### Deep Dives

- **[tier0-backpressure-deep-dive.md](tier0-backpressure-deep-dive.md)**
  - Full rationale and problem statement
  - All 4 backpressure mechanisms explained
  - Multi-repo integration strategies
  - Advancement context (Yegge's stages)

- **[tier0-flow-examples.md](tier0-flow-examples.md)** ⭐
  - Complete walkthrough of Ralph Loop + Quality Gates + Adversarial Review
  - Real-world before/after comparisons
  - Iteration-by-iteration flow
  - Integration with existing codebase

### Implementation

- **[../src/templates/README.md](../src/templates/README.md)**
  - Templates module API documentation
  - Usage examples (automatic and manual)
  - Language adaptations (Python/C#/TypeScript)
  - Testing guide

- **[../src/templates/examples.py](../src/templates/examples.py)**
  - Runnable code examples
  - Demonstrates all template features
  - Multi-language adaptation examples

## Quick Navigation

**I want to...**

- **Understand the big picture** → [tier0-backpressure-deep-dive.md](tier0-backpressure-deep-dive.md)
- **See it in action** → [tier0-flow-examples.md](tier0-flow-examples.md)
- **Use it right now** → [tier0-quick-reference.md](tier0-quick-reference.md)
- **Integrate into my code** → [../src/templates/README.md](../src/templates/README.md)
- **Run examples** → `python -m src.templates.examples`
- **Read tests** → [../tests/test_templates.py](../tests/test_templates.py)

## Tier Progression

```
✓ Tier 0: Backpressure & Verification (YOU ARE HERE)
  - Quality gates implemented
  - Completion manifest implemented
  - Integrated into context builder
  - Documentation complete

○ Tier 1: Task Decomposition Mastery (BLOCKED by Tier 0)
  - Break work into parallel-safe units
  - Identify integration contracts
  - Detect task dependencies

○ Tier 2: Multi-Agent Coordination (BLOCKED by Tier 1)
  - Branch-per-agent isolation
  - Contract-based integration
  - Conflict detection

○ Tier 3: Orchestrator Automation (BLOCKED by Tier 2)
  - Auto-decomposition
  - Feedback loops
  - The outer loop
```

## Remaining Tier 0 Tasks

To complete Tier 0, implement:

1. **agent-orchestrator-wc1** (P1): Integration entrypoint verification gate
2. **agent-orchestrator-67o** (P1): 3-phase execution (adversarial review)
3. **agent-orchestrator-6mv** (P2): Multi-repo integration verification

## Key Concepts

- **Backpressure** — Mechanisms that prevent agents from rushing through incomplete work
- **Quality Gates** — 5 specific rules that define "done" for every task
- **Completion Manifest** — Structured proof that forces honesty about integration and gaps
- **Adversarial Review** — Automated challenge to test quality (mutation testing via prompting)
- **Ralph Loop** — Fresh context per iteration, progress via git commits (Huntley)
- **Delete Test** — Proof of integration: "If I deleted X, Y would break"

## References

- [Geoffrey Huntley - Everything is a Ralph Loop](https://ghuntley.com/loop/)
- [Steve Yegge - Welcome to Gas Town](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04)
- [Yegge's Developer-Agent Evolution Model](https://justin.abrah.ms/blog/2026-01-08-yegge-s-developer-agent-evolution-model.html)

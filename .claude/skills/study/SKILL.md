---
name: study
description: Deep codebase study before taking action. Use when learning a new area, onboarding to unfamiliar code, or before planning implementation. Inspired by Geoffrey Huntley's Ralph methodology — study first, never assume.
argument-hint: [path-or-topic]
allowed-tools: Read, Grep, Glob, Task, WebFetch, WebSearch
context: fork
agent: Explore
---

# Study: Deep Codebase Analysis

You are performing a deep study of a codebase area. Your goal is to build a thorough mental model before any action is taken. **You are read-only. Do not modify anything.**

## Target

Study: $ARGUMENTS

## Method

### Phase 0: Orientation (parallel)

Launch parallel searches to establish context quickly:

0a. **Specs & docs** — Find and read any specifications, READMEs, design docs, or ADRs related to the target. Check `docs/`, `specs/`, `*.md` files near the target.

0b. **Implementation plan** — Look for IMPLEMENTATION_PLAN.md, TODO comments, open issues, or beads (`bd list`) that describe planned or in-progress work on this area.

0c. **Shared utilities** — Identify what shared libraries, helpers, or base classes the target depends on. Map the import graph.

0d. **Source code** — Read the actual implementation files for the target area.

### Phase 1: Analysis (synthesize findings)

After gathering context, analyze:

1. **Architecture** — How is this area structured? What patterns does it use? Draw the dependency graph (which modules depend on which).

2. **Data flow** — Trace how data moves through this area. What are the inputs, transformations, and outputs?

3. **Integration points** — Where does this area connect to the rest of the system? What would break if you changed it?

4. **Test coverage** — What tests exist? What's tested well vs. what has gaps? Run `Grep` for test files related to the target.

5. **Technical debt** — Look for TODOs, FIXMEs, placeholder implementations, skipped tests, inconsistent patterns.

## Critical Rules

- **NEVER assume something is missing.** Confirm with code search first. Search broadly — the implementation might live somewhere unexpected.
- **Treat shared code as canonical.** If a utility exists in a shared location, note it. Don't suggest reimplementing.
- **Be specific.** Reference exact file paths and line numbers. Quote relevant code snippets.
- **Surface surprises.** Flag anything that contradicts expectations, seems fragile, or has hidden complexity.

## Output Format

Structure your findings as:

```
## Study: [target]

### Overview
[1-2 sentence summary of what this area does]

### Architecture
[Structure, patterns, key files with paths]

### Data Flow
[How data moves through, inputs → outputs]

### Integration Points
[What connects to this, what would break]

### Test Coverage
[What's tested, what's not]

### Technical Debt & Risks
[TODOs, gaps, fragility, inconsistencies]

### Key Findings
[Numbered list of the most important things to know]
```

# Agent Orchestrator

## Vision
A CLI supervisor for AI coding agents, built to advance through Yegge's 8-stage developer-agent evolution model. Currently at Stage 5-6 (CLI, single/multi-agent) — targeting Stage 7-8 (hand-managed fleet, custom orchestrator).

Core principle: **single-agent reliability before multi-agent scale.** If your loop leaks incomplete work, more agents multiply the leak. Get one agent producing verified, integrated, tested code before adding parallelism.

Inspired by:
- Steve Yegge's Gas Town — multi-agent orchestration, trust escalation, the 8-stage model
- Geoffrey Huntley's Ralph Loop — fresh context per iteration, progress via artifacts not memory, brute-force persistence
- The shared insight: the hard problem isn't making agents code, it's making them produce *correct, complete, integrated* code

## Tier Progression
- **Tier 0** (now): Backpressure & verification — Ralph Loop, execution logging, adversarial review
- **Tier 1** (next): Task decomposition — splitting work into parallel-safe units
- **Tier 2** (then): Multi-agent coordination — contracts-first, branch-per-agent, conflict detection
- **Tier 3** (later): Orchestrator automation — auto-decomposition, feedback loops, the outer loop

Each tier is blocked by the previous. Don't skip ahead.

## Architecture
- `supervisor.py` — Entry point, delegates to execution strategies
- `src/models/` — Execution strategies (escalation, two-phase architect/intern)
- `src/verification/` — Multi-layer verification pipeline
- `src/preconditions/` — Pre-execution safety checks
- `src/context/` — Context file parsing and surgical context feeding
- `src/guards/` — Commit safety guards
- `src/shell/` — Shell execution, git utilities, retry logic

## Guinea Pig
`/home/wspradley/src/investing/my-investing` — a LangGraph + Claude investment analysis agent with real tests and complexity. Use it to validate orchestrator features against a real project.

## Workflow
This project uses `bd` (beads) for issue tracking. Run `bd ready` to find work.

**Session Completion Protocol:**
Work is NOT complete until changes are pushed. Before ending any session:
1. Create issues for remaining work (`bd create`)
2. Run quality gates if code changed (tests, linters)
3. Close finished issues (`bd close <id>`)
4. **Push to remote** (MANDATORY):
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # Must show "up to date with origin"
   ```

Never stop before pushing. If push fails, resolve and retry until it succeeds.

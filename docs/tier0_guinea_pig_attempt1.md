# Tier 0 Guinea Pig Validation: Attempt 1 Post-Mortem

**Date**: 2026-02-08
**Task**: my-investing-1tt - Add workflow-level logging to nodes and graph
**Ralph Loop Iterations**: 3 (all failed)
**Duration**: 34.6s
**Outcome**: FAILED - No code changes made

## Executive Summary

The first Tier 0 proof run revealed a critical gap: **the agent made zero code changes across all three iterations**, despite the supervisor executing correctly. This validates the orchestrator's detection capabilities (it correctly identified no progress) but exposes a failure mode where the agent receives tasks but produces no output.

## What Broke

### Agent Execution Failure
- All 3 iterations completed without producing code changes
- Only test fixtures were modified (timestamps updated from running pytest)
- Git diff showed binary database changes and test result timestamps, but no source code modifications
- Supervisor correctly detected "Agent made NO changes to repository" on each attempt

### Spec Tracker Results
All 5 acceptance criteria remained incomplete:
```
○ 1. Add logging to workflow.py for graph compilation and execution
○ 2. Add logging to scout node (entry/exit with ticker and confidence)
○ 3. Add logging to skeptic node (entry/exit with ticker and confidence)
○ 4. Add logging to adjudicator node (entry/exit with recommendation)
○ 5. All tests pass with 80%+ coverage
```

## What the Orchestrator Caught

### ✅ Verification Pipeline Working
- Spec tracker correctly identified incomplete work
- `git diff` analysis detected lack of meaningful changes
- Escalation protocol executed as designed (3 attempts with different models)
- Preconditions all passed:
  - Git working tree clean ✓
  - Agent reachable ✓
  - Tests exist ✓
  - Syntax valid ✓

### ✅ Safety Mechanisms Working
- Stash/pop safety snapshot prevented corruption
- Hard reset between attempts kept environment clean
- No partial/broken code left in repository

## What the Orchestrator Missed

### ❌ Agent Output Visibility
**CRITICAL GAP**: Zero visibility into what the agent actually received or produced.

Missing observability:
1. Was the prompt correctly formatted and passed to `claude` CLI?
2. Did the agent start execution?
3. Did it encounter an error (API, permissions, parsing)?
4. Did it produce output that got swallowed?
5. Did it think the task was complete despite making no changes?

**Impact**: Without agent stdout/stderr capture, impossible to diagnose why execution failed.

### ❌ Cross-Project Invocation Logs
- Ralph Loop ran from my-investing directory
- Supervisor invoked from agent-orchestrator directory (via absolute path)
- No logs produced in either location
- Claude session logs show earlier sessions (11:25-11:34) but not Ralph Loop runs (13:11-13:12)

### ❌ Prompt Effectiveness Testing
- No way to validate if the prompt was:
  - Clear enough for the agent to understand
  - Properly escaped/quoted for shell execution
  - Received by the agent intact

## Root Cause Analysis

### Primary Hypothesis: Agent Output Not Captured
The `supervisor.py` invokes the agent via `run_shell_with_retry()` which captures stdout/stderr, but:
- The Ralph Loop doesn't log agent output to disk
- Stdout from nested subprocess may not be captured correctly
- No explicit logging layer for agent communications

### Contributing Factors
1. **Silent Failure Mode**: Agent can fail without reporting errors to supervisor
2. **No Structured Logging**: Supervisor logs to stdout only, no persistent files
3. **Prompt Construction Opacity**: No way to inspect final prompt sent to agent
4. **Session Cleanup**: Claude agent sessions may be ephemeral in `-p` print mode

## Lessons Learned

### 1. Observability is Non-Negotiable
**Finding**: Can't debug what you can't see.

**Action Required**: Implement structured execution logging (see agent-orchestrator-vsf bead)
- Log every agent invocation: timestamp, model, prompt (truncated), cost
- Capture agent stdout/stderr to file
- Track verification outcomes with failure reasons

### 2. Ralph Loop Needs Diagnostic Mode
**Finding**: Fresh context per iteration is great for correctness, terrible for debugging.

**Action Required**:
- Add `--verbose` flag that preserves agent output between iterations
- Create `.ralph_log/` directory with per-iteration artifacts:
  - Prompt sent
  - Agent output
  - Git diff
  - Verification results

### 3. Spec Tracker Validates, Doesn't Diagnose
**Finding**: Spec checks tell you WHAT failed, not WHY.

**Action Required**:
- Enhance spec tracker with failure reason capture
- Add diagnostic commands that run on failure (e.g., `git status`, file existence checks)

### 4. Cross-Project Invocation Complexity
**Finding**: Running supervisor.py from a different project (my-investing) than its home (agent-orchestrator) creates log/session ambiguity.

**Resolution**: Recent fix (commit 1a9c462) made Ralph Loop cross-project capable with `find_supervisor()` auto-detection. This part worked correctly.

## Next Steps

### Immediate (Before Retry)
1. **Implement agent-orchestrator-vsf**: Structured execution logging
   - Log agent invocations to `.ralph_logs/iteration_N/`
   - Capture full prompt, output, and verification results
   - Add timestamps and cost tracking

2. **Add Diagnostic Flag to Ralph Loop**:
   ```python
   --diagnose: Keep full agent output, don't suppress errors
   ```

3. **Manual Test**: Run supervisor.py directly with verbose output
   ```bash
   cd /home/wspradley/src/investing/my-investing
   /home/wspradley/src/agent-orchestrator/supervisor.py \
     "Add workflow-level logging" \
     --verify "pytest --cov=src --cov-fail-under=80 -q" 2>&1 | tee supervisor.log
   ```

### Tier 0 Validation (Before Advancing)
- [ ] Re-run Ralph Loop with logging enabled
- [ ] Verify we can see agent prompts, outputs, and errors
- [ ] Confirm at least one real my-investing task completes end-to-end
- [ ] Document what worked, what broke, what was caught

### Tier 1 Readiness Gate
**BLOCKER**: Do NOT proceed to Tier 1 (task decomposition) until:
1. Tier 0 proof shows successful completion of ≥1 real my-investing task
2. Execution logging provides full observability
3. Verification pipeline catches real failures (not just no-op cases)

## Conclusion

**Tier 0 Proof Status**: ❌ FAILED (Expected - first attempt)

**Value Delivered**: Exposed critical observability gap before it could multiply in multi-agent scenarios.

**Key Insight**: The orchestrator's *mechanics* work (preconditions, safety, verification), but without visibility into agent execution, it's flying blind. Logging is not a nice-to-have, it's load-bearing infrastructure.

**Next Action**: Implement agent-orchestrator-vsf (structured logging), then retry with observability.

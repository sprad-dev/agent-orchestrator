# Agent Orchestrator

A specialized CLI tool for supervising AI coding agents with surgical context management and intelligent model escalation.

## Features

### Two-Phase Test-Driven Execution (Architect vs Intern)

The supervisor supports a two-phase execution model where an expensive "architect" model writes tests and a cheap "intern" model implements the code. This is the highest-leverage optimization technique.

**Strategy:**

- **Phase 1 (Smart Model)**: Generates comprehensive pytest tests that specify exact behavior
- **Phase 2 (Cheap Model)**: Implements minimal code to make tests pass via Red-Green-Refactor

**Usage:**

```bash
# Two-phase mode with smart test generation and cheap implementation
./supervisor.py "Add user authentication" \
  --test-model "claude-4.5-sonnet" \
  --impl-model "claude-4.5-haiku"
```

**Benefits:**

- **Massive cost reduction**: Haiku handles implementation (bulk of tokens)
- **Quality tests**: Sonnet/Opus writes correct specifications
- **Test-driven**: Tests committed first as backpressure artifacts
- **Clear separation**: Architecture thinking vs mechanical implementation

### Escalation Protocol (Try-Catch Pattern)

The supervisor implements intelligent model escalation - starting with cheaper models and automatically escalating to more powerful models only on failure.

**Usage:**

```bash
# Use default escalation chain (haiku → haiku → sonnet)
./supervisor.py "Add feature"

# Custom escalation chain
./supervisor.py "Fix bug" --models "claude-4.5-haiku,claude-4.5-sonnet,claude-4.5-opus"

# Single model (no escalation)
./supervisor.py "Simple fix" --models "claude-4.5-haiku"
```

**Benefits:**

- **Cost optimization**: Cheap models handle simple tasks (80%+ of work)
- **Smart fallback**: Escalates automatically when cheap models fail
- **Early exit**: Stops at first success, doesn't waste expensive tokens
- **Transparent**: Logs show which model solved the task

### Context Pruning (Malloc Discipline)

The supervisor implements surgical context feeding - only providing agents with files they need for the specific task, avoiding token waste and performance degradation.

**Usage:**

Specify context files explicitly in your task:

```bash
# JSON format
./supervisor.py "Fix bug context_files: [\"file1.py\", \"file2.py\"]"

# Inline format  
./supervisor.py "Fix bug [context: file1.py, file2.py]"
```

**Auto-detection:**

If no context is specified, the supervisor automatically detects Python files mentioned in the task and includes their corresponding test files:

```bash
# Automatically loads calculator.py and test_calculator.py
./supervisor.py "Fix bug in calculator.py"
```

**Benefits:**

- **Reduced token usage**: Only relevant files are loaded
- **Improved focus**: Agents aren't distracted by irrelevant code
- **Better performance**: Less context to process means faster responses
- **Cost savings**: Fewer tokens = lower API costs

## Agent Workflow Analysis

📊 **New:** Comprehensive analysis of how codebase modularity impacts agent-based development workflows.

### Key Findings
- **Context Bloat:** 1,855 tokens wasted per agent task
- **Parallelization Blocked:** 5 issues prevent concurrent agent development
- **Agent Success Rate:** 67% baseline (33% failure rate due to complexity)

### Quick Wins Available
**Phase 1 (4 hours)** saves 880 tokens and enables 3× parallel agents:
- Issue #8: Move tests to `tests/` directory (1 hour, 400 tokens saved)
- Issue #1: Extract BaseExecutor interface (2 hours, 300 tokens saved)
- Issue #7: Create LayerCoordinator (1 hour, 180 tokens saved)

**ROI:** 0.6 week payback period, 8667% annual return

### Documentation
- **Executive Summary:** [docs/EXECUTIVE_SUMMARY_AGENT_IMPACT.md](docs/EXECUTIVE_SUMMARY_AGENT_IMPACT.md)
- **Full Analysis:** [docs/agent-workflow-impact-analysis.md](docs/agent-workflow-impact-analysis.md)
- **Quick Reference:** [docs/agent-impact-matrix.md](docs/agent-impact-matrix.md)

### Interactive Calculator
```bash
# View all 12 issues ranked by agent impact
python calculate_agent_impact.py

# Detailed report for specific issue
python calculate_agent_impact.py --issue 8

# Simulate phased refactoring
python calculate_agent_impact.py --simulate
```

## Basic Usage

```bash
./supervisor.py "your task description" --agent "your-agent {prompt}" --verify "pytest"
```

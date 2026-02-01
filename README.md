# Agent Orchestrator

A specialized CLI tool for supervising AI coding agents with surgical context management and intelligent model escalation.

## Features

### Escalation Protocol (Try-Catch Pattern)

The supervisor implements intelligent model escalation - starting with cheaper models and automatically escalating to more powerful models only on failure.

**Usage:**

```bash
# Use default escalation chain (haiku → haiku → sonnet)
./supervisor.py "Add feature"

# Custom escalation chain
./supervisor.py "Fix bug" --models "claude-3-haiku,claude-3-5-sonnet,claude-opus-4"

# Single model (no escalation)
./supervisor.py "Simple fix" --models "claude-3-haiku"
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

## Basic Usage

```bash
./supervisor.py "your task description" --agent "your-agent {prompt}" --verify "pytest"
```

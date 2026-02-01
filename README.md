# Agent Orchestrator

A specialized CLI tool for supervising AI coding agents with surgical context management.

## Features

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

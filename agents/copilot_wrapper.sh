#!/bin/bash
# Wrapper for GitHub Copilot CLI to work with supervisor.py
#
# Usage: copilot_wrapper.sh "prompt text"
#
# This wraps gh copilot to provide a consistent interface with claude CLI.

PROMPT="$1"

if [ -z "$PROMPT" ]; then
    echo "Error: No prompt provided" >&2
    exit 1
fi

# Check if gh copilot is available
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) not installed" >&2
    echo "Install: https://cli.github.com/" >&2
    exit 1
fi

if ! gh copilot --version &> /dev/null 2>&1; then
    echo "Error: GitHub Copilot CLI extension not installed" >&2
    echo "Install: gh extension install github/gh-copilot" >&2
    exit 1
fi

# Use gh copilot suggest with shell target type
# This generates shell commands that can implement the task
gh copilot suggest -t shell "$PROMPT"

# Copilot CLI is interactive, so this wrapper may need adjustment
# For now, it outputs the suggestion
exit 0

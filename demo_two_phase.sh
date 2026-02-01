#!/bin/bash
# Demo script for two-phase test-driven execution
# Shows the architect/intern split in action

set -e

echo "=== Two-Phase Test-Driven Execution Demo ==="
echo ""
echo "This demonstrates the architect vs intern pattern:"
echo "  - Smart model (Sonnet) writes comprehensive tests"
echo "  - Cheap model (Haiku) implements code to pass tests"
echo ""

# Example 1: Simple function
echo "--- Example 1: String Reverser ---"
echo "Task: Create a function that reverses strings"
echo ""

./supervisor.py \
  "Create a string_utils.py module with a reverse_string() function that reverses a string" \
  --test-model "claude-3-5-sonnet" \
  --impl-model "claude-3-haiku" \
  --agent "./mock_agent.sh {prompt}" \
  --verify "pytest test_string_utils.py"

echo ""
echo "✅ Two-phase execution complete!"
echo ""
echo "Benefits:"
echo "  - Tests specify exact behavior (written by Sonnet)"
echo "  - Implementation is mechanical (handled by Haiku)"
echo "  - Massive token cost reduction vs single expensive model"
echo ""

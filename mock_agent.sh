#!/bin/bash
# Mock agent that fixes the calculator.py file

echo "🤖 Mock Agent: Received task: $1"
echo "🤖 Implementing the add function..."

cat > calculator.py << 'EOF'
def add(a, b):
    """Add two numbers together."""
    return a + b
EOF

echo "✅ Mock Agent: Fixed calculator.py"

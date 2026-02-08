# Agent Configurations

This directory contains agent wrappers and configurations for different LLM providers.

## Supported Agents

### Claude Code (Primary)

The default agent. Uses Anthropic's Claude via the official CLI.

```bash
# Command template
claude {prompt}

# Usage in Ralph Loop (default)
./ralph_loop.py "Task description"
```

**Pros:**
- Best code quality
- Good at following instructions
- Tool use and artifacts support

**Cons:**
- Rate limits on free tier
- Requires API key

### GitHub Copilot CLI (Fallback)

Uses GitHub Copilot's CLI for code suggestions.

```bash
# Installation
gh extension install github/gh-copilot

# Command template
gh copilot suggest -t shell {prompt}

# Usage in Ralph Loop
./ralph_loop.py "Task description" \
  --fallback-agents "gh copilot suggest -t shell {prompt}"
```

**Pros:**
- Included with GitHub Copilot subscription
- Fast responses
- Good for shell commands and quick fixes

**Cons:**
- Interactive by default (may need wrapper)
- Less capable for complex refactoring
- Designed for suggestions, not full implementations

### Other Options

#### Aider

AI pair programming tool with direct file editing.

```bash
# Installation
pip install aider-chat

# Command template
aider --yes --message {prompt}

# Usage
./ralph_loop.py "Task" \
  --agent "aider --yes --message {prompt}"
```

#### OpenAI API (Direct)

Custom wrapper using OpenAI API directly.

```bash
# Create wrapper: agents/openai_wrapper.py
python agents/openai_wrapper.py {prompt}

# Usage
./ralph_loop.py "Task" \
  --agent "python agents/openai_wrapper.py {prompt}"
```

## Creating Custom Wrappers

To add a new LLM provider:

1. Create a wrapper script in `agents/`
2. Accept prompt as first argument
3. Output code changes or execute them directly
4. Exit with 0 on success, non-zero on failure

Example wrapper template:

```bash
#!/bin/bash
# agents/my_llm_wrapper.sh

PROMPT="$1"

# 1. Call your LLM API
response=$(curl -X POST https://api.example.com/chat \
  -H "Authorization: Bearer $API_KEY" \
  -d "{\"prompt\": \"$PROMPT\"}")

# 2. Extract code and apply changes
# ... implementation ...

# 3. Exit with appropriate code
exit 0
```

## Fallback Chain Examples

### Claude → Copilot → Aider

```bash
./ralph_loop.py "Implement feature X" \
  --agent "claude {prompt}" \
  --fallback-agents "gh copilot suggest -t shell {prompt},aider --yes --message {prompt}"
```

### Budget-Conscious: Free Tier → Paid Tier

```bash
./ralph_loop.py "Task" \
  --agent "claude {prompt}" \
  --max-cost 0.10 \
  --fallback-agents "gpt4-api-wrapper {prompt}"
```

### Multi-Model Validation

Different models for different purposes:

```bash
# Claude for architecture, Copilot for implementation
./ralph_loop.py "Design + implement feature" \
  --agent "claude {prompt}" \
  --fallback-agents "gh copilot suggest -t shell {prompt}"
```

## Rate Limit Handling

The Ralph Loop automatically detects rate limits and switches to fallbacks when it sees:

- `rate limit exceeded`
- `usage limit`
- `quota exceeded`
- `429` HTTP status
- `budget exceeded`

This means you can set a budget on Claude and automatically fall back to Copilot:

```bash
./ralph_loop.py "Large refactoring task" \
  --max-cost 0.50 \
  --agent "claude {prompt}" \
  --fallback-agents "gh copilot suggest -t shell {prompt}"
```

When Claude hits the $0.50 limit, Ralph Loop switches to Copilot automatically.

## Testing Agents

Test your agent wrapper:

```bash
# Direct test
./agents/copilot_wrapper.sh "Write a Python function to reverse a string"

# Via supervisor
./supervisor.py "Simple task" --agent "gh copilot suggest -t shell {prompt}"

# Via Ralph Loop
./ralph_loop.py "Test task" --agent "your-wrapper {prompt}" --max-iterations 1
```

## Best Practices

1. **Primary = Best Quality**: Use Claude or GPT-4 as primary for best results
2. **Fallback = Good Enough**: Use faster/cheaper models as fallbacks
3. **Budget Limits**: Set `--max-cost` to trigger fallbacks before breaking the bank
4. **Test First**: Verify fallback agents work before relying on them
5. **Monitor Stats**: Use `./supervisor.py --stats` to see which agents perform best

## Troubleshooting

**Copilot returns empty responses:**
- The CLI is interactive by default
- Use wrapper script to handle prompts non-interactively
- Or use Copilot API if available

**Agent not found:**
- Ensure the tool is installed and in PATH
- Test the command directly first
- Check wrapper script permissions (chmod +x)

**Fallback not triggering:**
- Check that primary agent is actually failing
- Verify error messages contain rate limit indicators
- Use `--max-cost` to force budget limits

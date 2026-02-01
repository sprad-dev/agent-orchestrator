"""Shell command execution and git operations.

This module handles:
- Running shell commands with error handling
- Git status and diff operations
- Working directory awareness
"""

import subprocess
import shlex
from typing import Tuple, Optional


def run_shell(cmd: str, ignore_error: bool = False, timeout: Optional[int] = None) -> Tuple[bool, str, int]:
    """Runs a command in the CURRENT working directory.

    Args:
        cmd: Shell command string to execute
        ignore_error: If True, don't raise on non-zero exit
        timeout: Maximum seconds to wait (default: None = no timeout)

    Returns:
        Tuple of (success: bool, output: str, returncode: int)
    """
    timeout_str = f" (timeout: {timeout}s)" if timeout else ""
    print(f" [exec]{timeout_str} {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=not ignore_error,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        success = result.returncode == 0
        return success, result.stdout, result.returncode
    except subprocess.TimeoutExpired as e:
        error_msg = f"Command timed out after {timeout} seconds"
        output = e.stdout.decode() if e.stdout else ""
        output += "\n" + (e.stderr.decode() if e.stderr else "")
        output += f"\n\n[TIMEOUT] {error_msg}"
        print(f" [X] {error_msg}")
        return False, output, -1
    except subprocess.CalledProcessError as e:
        return False, e.stderr + e.stdout, e.returncode


def has_changes() -> bool:
    """Check if there are any uncommitted changes in the working directory."""
    success, output, _ = run_shell("git status --porcelain", ignore_error=True)
    return success and len(output.strip()) > 0


def get_diff_summary() -> str:
    """Get a summary of changes made."""
    success, output, _ = run_shell("git diff --stat", ignore_error=True)
    return output if success else "Unable to get diff"


def get_diff_content() -> str:
    """Get the full diff of current changes."""
    success, output, _ = run_shell("git diff", ignore_error=True)
    return output if success else "Unable to get diff"


def truncate_error(error_text: str, max_length: int = 2000) -> str:
    """Truncate error text to prevent unbounded output.

    Keeps first half and last half with ellipsis in middle.

    Args:
        error_text: The error text to truncate
        max_length: Maximum length (default: 2000)

    Returns:
        Truncated string with first/last chunks if over limit

    Example:
        >>> truncate_error("x" * 5000, 2000)
        'xxx...xxx'  # first 1000 + "..." + last 1000
    """
    if not error_text or len(error_text) <= max_length:
        return error_text

    chunk_size = max_length // 2
    first_chunk = error_text[:chunk_size]
    last_chunk = error_text[-chunk_size:]

    return f"{first_chunk}\n...[truncated {len(error_text) - max_length} chars]...\n{last_chunk}"


def build_agent_command(template: str, prompt: str, model: str) -> str:
    """Build agent command with properly escaped prompt.

    This eliminates code duplication across execution strategies by
    centralizing the prompt escaping and template substitution logic.

    Args:
        template: Agent command template with {prompt} and {model} placeholders
        prompt: The prompt text to send to the agent
        model: The model identifier to use

    Returns:
        Fully constructed agent command string with escaped prompt

    Example:
        >>> build_agent_command("claude {prompt}", "Fix bug", "sonnet")
        "claude 'Fix bug'"
    """
    safe_prompt = shlex.quote(prompt)
    return template.replace("{prompt}", safe_prompt).replace("{model}", model)

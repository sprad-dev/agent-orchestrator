"""Shell command execution and git operations.

This module handles:
- Running shell commands with error handling
- Git status and diff operations
- Working directory awareness
- Exponential backoff retry for transient failures
"""

import subprocess
import shlex
import time
import random
from typing import Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.cost_tracker import AgentCostTracker


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


def _is_transient_failure(returncode: int, output: str) -> bool:
    """Detect if a failure is transient and worth retrying.

    Args:
        returncode: Command exit code
        output: Command output (stdout + stderr)

    Returns:
        True if the failure appears transient (network, rate limit, etc.)
    """
    # Timeout is always transient
    if returncode == -1:
        return True

    # Check for common transient error patterns in output
    transient_patterns = [
        "connection refused",
        "connection reset",
        "temporarily unavailable",
        "timed out",
        "timeout",
        "rate limit",
        "429",  # HTTP 429 Too Many Requests
        "503",  # HTTP 503 Service Unavailable
        "network error",
        "dns",
        "could not resolve host",
        "failed to connect",
    ]

    output_lower = output.lower()
    return any(pattern in output_lower for pattern in transient_patterns)


def run_shell_with_retry(
    cmd: str,
    ignore_error: bool = False,
    timeout: Optional[int] = None,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    cost_tracker: Optional["AgentCostTracker"] = None,
    model: Optional[str] = None,
    phase: str = "execution",
    attempt_num: int = 1
) -> Tuple[bool, str, int]:
    """Run shell command with exponential backoff retry on transient failures.

    This wraps run_shell() with retry logic for transient failures like:
    - Network timeouts
    - Connection errors
    - Rate limits (429)
    - Temporary unavailability (503)

    Args:
        cmd: Shell command string to execute
        ignore_error: If True, don't raise on non-zero exit
        timeout: Maximum seconds to wait per attempt (default: None)
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        backoff_multiplier: Multiplier for exponential backoff (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        jitter: Add random jitter to delays to avoid thundering herd (default: True)
        cost_tracker: Optional AgentCostTracker for tracking token usage/costs
        model: Model identifier for cost tracking (required if cost_tracker provided)
        phase: Execution phase for cost tracking (default: "execution")
        attempt_num: Attempt number for cost tracking (default: 1)

    Returns:
        Tuple of (success: bool, output: str, returncode: int)

    Raises:
        BudgetExceededException: If cost/token budget is exceeded

    Example:
        # Retry up to 3 times with exponential backoff
        success, output, code = run_shell_with_retry(
            "claude 'Fix the bug'",
            timeout=300,
            max_retries=3
        )
    """
    attempt = 0
    delay = initial_delay
    start_time = time.time()

    while attempt <= max_retries:
        exec_start = time.time()
        success, output, returncode = run_shell(cmd, ignore_error=True, timeout=timeout)
        exec_duration = time.time() - exec_start

        # Track cost/tokens if tracker provided
        if cost_tracker and model:
            from ..models.cost_tracker import parse_claude_tokens, BudgetExceededException

            tokens = parse_claude_tokens(output)
            if tokens:
                input_tokens, output_tokens = tokens
                try:
                    cost_tracker.record_execution(
                        model=model,
                        phase=phase,
                        attempt_num=attempt_num,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        duration_seconds=exec_duration,
                        success=success,
                        retry_count=attempt
                    )
                except BudgetExceededException as e:
                    # Budget exceeded - propagate exception
                    print(f" [X] {str(e)}")
                    raise

        # Success - return immediately
        if success:
            return success, output, returncode

        # Check if this is a transient failure worth retrying
        is_transient = _is_transient_failure(returncode, output)

        # If not transient, or we've exhausted retries, return failure
        if not is_transient or attempt >= max_retries:
            if not ignore_error and not is_transient:
                # Non-transient failure - propagate error
                return success, output, returncode
            # Either ignore_error=True or we exhausted retries
            return success, output, returncode

        # Transient failure - retry with backoff
        attempt += 1
        current_delay = min(delay, max_delay)

        # Add jitter to avoid thundering herd
        if jitter:
            current_delay *= (0.5 + random.random())  # Random factor between 0.5 and 1.5

        print(f" [retry] Attempt {attempt}/{max_retries} after {current_delay:.1f}s (transient failure detected)")
        time.sleep(current_delay)

        # Exponential backoff for next iteration
        delay *= backoff_multiplier

    # Should not reach here, but return last result
    return success, output, returncode


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

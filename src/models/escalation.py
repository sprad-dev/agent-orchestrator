"""Escalation protocol execution strategy.

This module implements the try-catch waterfall pattern:
- Start with cheapest model (Haiku)
- Escalate to more capable models on failure
- Each retry uses diff-only feedback to prevent context rot

This optimizes cost by only using expensive models when needed.
"""

import os
import shlex
import time
from typing import List, Optional

from src.context import build_static_context, parse_context_files, get_default_context_files
from src.shell import (
    run_shell,
    run_shell_with_retry,
    has_changes,
    get_diff_summary,
    get_diff_content,
    truncate_error,
    build_agent_command,
)
from src.preconditions import check_git_clean, check_agent_reachable, check_tests_exist, check_syntax
from src.models.cost_tracker import AgentCostTracker, BudgetExceededException


DEFAULT_MODELS = ["claude-4.5-haiku", "claude-4.5-haiku", "claude-4.5-sonnet"]
DEFAULT_AGENT_TIMEOUT = 300  # 5 minutes
DEFAULT_EXECUTION_TIMEOUT = 1800  # 30 minutes total execution time


class EscalationExecutor:
    """Executes tasks using model escalation on failure."""

    def __init__(
        self,
        agent_cmd_template: str,
        verify_cmd: str,
        models: Optional[List[str]] = None,
        agent_timeout: int = DEFAULT_AGENT_TIMEOUT,
        execution_timeout: Optional[int] = DEFAULT_EXECUTION_TIMEOUT,
        max_cost_per_run: Optional[float] = None,
        max_tokens_per_run: Optional[int] = None
    ) -> None:
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.models = models if models else DEFAULT_MODELS
        self.agent_timeout = agent_timeout
        self.execution_timeout = execution_timeout
        self.max_cost_per_run = max_cost_per_run
        self.max_tokens_per_run = max_tokens_per_run

    def _check_timeout(self, start_time: float) -> bool:
        """Check if execution has exceeded timeout limit.

        Returns:
            True if timeout exceeded, False otherwise
        """
        if self.execution_timeout is None:
            return False

        elapsed = time.time() - start_time
        if elapsed >= self.execution_timeout:
            print(f"\n [!] EXECUTION TIMEOUT: {elapsed:.1f}s >= {self.execution_timeout}s")
            return True
        return False

    def _print_cost_summary(self, cost_tracker: AgentCostTracker, start_time: float) -> None:
        """Print execution cost summary.

        Args:
            cost_tracker: Cost tracker instance
            start_time: Execution start time
        """
        elapsed = time.time() - start_time
        summary = cost_tracker.get_run_summary()

        print("\n--- EXECUTION SUMMARY ---")
        print(f"Total Duration: {elapsed:.1f}s")
        print(f"Total Cost: ${summary['total_cost_usd']:.4f}")
        print(f"Total Tokens: {summary['total_tokens']:,}")

        if 'cost_budget_remaining_usd' in summary:
            print(f"Cost Budget Used: {summary['cost_budget_used_percent']:.1f}% "
                  f"(${summary['cost_budget_remaining_usd']:.4f} remaining)")

        if 'token_budget_remaining' in summary:
            print(f"Token Budget Used: {summary['token_budget_used_percent']:.1f}% "
                  f"({summary['token_budget_remaining']:,} remaining)")

        # Model breakdown
        by_model = cost_tracker.get_cost_by_model()
        if by_model:
            print("\nCost by Model:")
            for model, cost in sorted(by_model.items(), key=lambda x: x[1], reverse=True):
                print(f"  {model}: ${cost:.4f}")

    def execute(self, task: str) -> bool:
        """Execute task with escalation protocol."""
        start_time = time.time()

        # Initialize cost tracker
        cost_tracker = AgentCostTracker(
            max_cost_per_run=self.max_cost_per_run,
            max_tokens_per_run=self.max_tokens_per_run
        )
        cost_tracker.reset_run_budget()

        print(f"--- SUPERVISOR STARTED ---")
        print(f"Target: {os.getcwd()}")
        print(f"Task: {task}")
        print(f"Escalation Chain: {' -> '.join(self.models)}")
        if self.execution_timeout:
            print(f"Execution Timeout: {self.execution_timeout}s (wall-clock)")
        if self.max_cost_per_run:
            print(f"Cost Budget: ${self.max_cost_per_run:.4f}")
        if self.max_tokens_per_run:
            print(f"Token Budget: {self.max_tokens_per_run:,}")

        # Preconditions
        print("\n [Preconditions] Running safety checks...")

        # Check 1: Git working tree is clean
        try:
            result = check_git_clean()
            if not isinstance(result, tuple) or len(result) != 2:
                print(f" [X] CRITICAL: check_git_clean returned invalid type: {type(result)}")
                return False
            passed, message = result
            if not passed:
                print(f" [X] Git clean check failed: {message}")
                print("     Commit or stash changes before running supervisor.")
                return False
            print(f" [✓] {message}")
        except Exception as e:
            print(f" [X] CRITICAL: check_git_clean raised exception: {e}")
            return False

        # Check 2: Agent is reachable
        try:
            result = check_agent_reachable(self.agent_cmd_template)
            if not isinstance(result, tuple) or len(result) != 2:
                print(f" [X] CRITICAL: check_agent_reachable returned invalid type: {type(result)}")
                return False
            passed, message = result
            if not passed:
                print(f" [X] Agent reachable check failed: {message}")
                return False
            print(f" [✓] {message}")
        except Exception as e:
            print(f" [X] CRITICAL: check_agent_reachable raised exception: {e}")
            return False

        # Check 3: Tests exist and are collectible
        try:
            result = check_tests_exist(self.verify_cmd)
            if not isinstance(result, tuple) or len(result) != 2:
                print(f" [X] CRITICAL: check_tests_exist returned invalid type: {type(result)}")
                return False
            passed, message = result
            if not passed:
                print(f" [X] Tests exist check failed: {message}")
                return False
            print(f" [✓] {message}")
        except Exception as e:
            print(f" [X] CRITICAL: check_tests_exist raised exception: {e}")
            return False

        # Check 4: Python syntax validation (all .py files)
        try:
            result = check_syntax()  # Checks all Python files in repo
            if not isinstance(result, tuple) or len(result) != 2:
                print(f" [X] CRITICAL: check_syntax returned invalid type: {type(result)}")
                return False
            passed, message = result
            if not passed:
                print(f" [X] Syntax check failed: {message}")
                print("     Fix syntax errors before running agent to avoid wasted cycles.")
                return False
            print(f" [✓] {message}")
        except Exception as e:
            print(f" [X] CRITICAL: check_syntax raised exception: {e}")
            return False

        # Parse context files from task
        context_files = parse_context_files(task)
        if context_files is None:
            context_files = get_default_context_files(task)

        if context_files:
            print(f" [Context] Loading {len(context_files)} file(s): {', '.join(context_files)}")
        else:
            print(f" [Context] No context files specified or detected")

        # Build static context once for caching optimization
        static_context, context_size = build_static_context(context_files)
        if context_size > 0:
            print(f" [Cache] Static context: {context_size:,} bytes (cacheable)")

        # Check timeout after preconditions
        if self._check_timeout(start_time):
            print(" [!] Timeout during preconditions. Aborting.")
            return False

        # Safety Snapshot
        print(" [1/5] Stashing clean state...")
        run_shell("git stash push -m 'Orchestrator Safety Snapshot'", ignore_error=True)

        last_error = None

        # Escalation Protocol: Try each model in sequence
        for model_idx, model in enumerate(self.models):
            # Check timeout before starting new attempt
            if self._check_timeout(start_time):
                print(f"\n [!] Execution timeout exceeded before attempt {model_idx + 1}. Reverting.")
                run_shell("git stash pop", ignore_error=True)
                return False

            attempt = model_idx + 1
            print(f"\n--- ATTEMPT {attempt}/{len(self.models)} [Model: {model}] ---")

            # Build prompt based on attempt
            if attempt == 1:
                # Initial attempt - include full static context
                dynamic_task = f"\n=== SPECIFIC TASK (Dynamic) ===\n{task}"
                full_task = f"{static_context}{dynamic_task}"
            else:
                # RETRY ATTEMPT: Use diff-only feedback
                print(f" [Diff-Only] Using minimal retry context (no conversation history)")

                diff_content = get_diff_content()
                retry_prompt = f"""Previous attempt failed. Using diff-only feedback to prevent context rot.

=== GOAL ===
{task}

=== CODE ATTEMPTED (Git Diff) ===
{diff_content if diff_content else "(No changes were made)"}

=== ERROR OUTPUT ===
{truncate_error(last_error) if last_error else "No error captured"}

Fix the error and implement correctly. Think step-by-step."""

                full_task = retry_prompt

            agent_cmd = build_agent_command(self.agent_cmd_template, full_task, model)

            # Capture HEAD before agent runs (for auto-commit detection)
            _, pre_head, _ = run_shell("git rev-parse HEAD", ignore_error=True)
            pre_agent_head = pre_head.strip() if pre_head else None

            print(f" [2/5] Unleashing Agent ({model}) [timeout: {self.agent_timeout}s]...")
            try:
                agent_success, agent_output, _ = run_shell_with_retry(
                    agent_cmd,
                    ignore_error=True,
                    timeout=self.agent_timeout,
                    max_retries=3,
                    initial_delay=1.0,
                    backoff_multiplier=2.0,
                    max_delay=60.0,
                    jitter=True,
                    cost_tracker=cost_tracker,
                    model=model,
                    phase="escalation",
                    attempt_num=attempt
                )
            except BudgetExceededException as e:
                print(f"\n [!] Budget exceeded: {str(e)}")
                print(" [!] Reverting changes and aborting execution.")
                run_shell(f"git reset --hard {pre_agent_head}" if pre_agent_head else "git reset --hard HEAD", ignore_error=True)
                run_shell("git clean -fd", ignore_error=True)
                run_shell("git stash pop", ignore_error=True)
                self._print_cost_summary(cost_tracker, start_time)
                return False

            if not has_changes(pre_agent_head):
                print(" [X] Agent made NO changes to repository!")
                print("     This likely means the agent failed or couldn't understand the task.")
                last_error = "Agent produced no output changes. Check if task is clear or agent is working."

                print(" [!] Resetting to clean state for retry...")
                run_shell(f"git reset --hard {pre_agent_head}" if pre_agent_head else "git reset --hard HEAD", ignore_error=True)
                run_shell("git clean -fd", ignore_error=True)
                continue

            print(" [3/5] Changes detected:")
            print(get_diff_summary(pre_agent_head))

            # Check timeout before verification
            if self._check_timeout(start_time):
                print(f"\n [!] Execution timeout exceeded before verification. Reverting.")
                run_shell(f"git reset --hard {pre_agent_head}" if pre_agent_head else "git reset --hard HEAD", ignore_error=True)
                run_shell("git clean -fd", ignore_error=True)
                run_shell("git stash pop", ignore_error=True)
                return False

            # Verify
            print(f" [4/5] Running Verifier: {self.verify_cmd}")
            passed, output, _ = run_shell(self.verify_cmd, ignore_error=True)

            if passed:
                print(f" [5/5] SUCCESS! Verification passed with {model}.")
                safe_task = shlex.quote(f'Agent ({model}): {task}')
                commit_success, commit_output, _ = run_shell(
                    f"git add . && git commit -m {safe_task}",
                    ignore_error=True
                )

                if commit_success:
                    print(f"       Changes committed successfully (solved by {model})")
                    run_shell("git stash drop", ignore_error=True)
                    self._print_cost_summary(cost_tracker, start_time)
                    return True
                else:
                    # Agent may have auto-committed — that's still a success
                    _, current_head, _ = run_shell("git rev-parse HEAD", ignore_error=True)
                    if current_head and current_head.strip() != pre_agent_head:
                        print(f"       Agent auto-committed changes (solved by {model})")
                        run_shell("git stash drop", ignore_error=True)
                        self._print_cost_summary(cost_tracker, start_time)
                        return True
                    print(f" [X] Commit failed: {truncate_error(commit_output)}")
                    run_shell("git stash drop", ignore_error=True)
                    self._print_cost_summary(cost_tracker, start_time)
                    return False
            else:
                print(" [X] FAILURE. Output snippet:")
                print(f"---\n{truncate_error(output)}...\n---")
                last_error = output

                print(" [!] Resetting to clean state for retry...")
                run_shell(f"git reset --hard {pre_agent_head}" if pre_agent_head else "git reset --hard HEAD", ignore_error=True)
                run_shell("git clean -fd", ignore_error=True)

        print(f"\n [!] Task failed after {len(self.models)} model(s). Reverting to start.")
        run_shell("git stash pop", ignore_error=True)
        self._print_cost_summary(cost_tracker, start_time)
        return False

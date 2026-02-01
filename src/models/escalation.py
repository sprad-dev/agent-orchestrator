"""Escalation protocol execution strategy.

This module implements the try-catch waterfall pattern:
- Start with cheapest model (Haiku)
- Escalate to more capable models on failure
- Each retry uses diff-only feedback to prevent context rot

This optimizes cost by only using expensive models when needed.
"""

import os
import shlex

from src.context import build_static_context, parse_context_files, get_default_context_files
from src.shell import run_shell, has_changes, get_diff_summary, get_diff_content, truncate_error
from src.preconditions import check_git_clean, check_agent_reachable, check_tests_exist


DEFAULT_MODELS = ["claude-4.5-haiku", "claude-4.5-haiku", "claude-4.5-sonnet"]
DEFAULT_AGENT_TIMEOUT = 300  # 5 minutes


class EscalationExecutor:
    """Executes tasks using model escalation on failure."""

    def __init__(self, agent_cmd_template, verify_cmd, models=None, agent_timeout=DEFAULT_AGENT_TIMEOUT):
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.models = models if models else DEFAULT_MODELS
        self.agent_timeout = agent_timeout

    def execute(self, task):
        """Execute task with escalation protocol."""
        print(f"--- SUPERVISOR STARTED ---")
        print(f"Target: {os.getcwd()}")
        print(f"Task: {task}")
        print(f"Escalation Chain: {' -> '.join(self.models)}")

        # Preconditions
        print("\n [Preconditions] Running safety checks...")
        
        # Check 1: Git working tree is clean
        passed, message = check_git_clean()
        if not passed:
            print(f" [X] Git clean check failed: {message}")
            print("     Commit or stash changes before running supervisor.")
            return False
        print(f" [✓] {message}")
        
        # Check 2: Agent is reachable
        passed, message = check_agent_reachable(self.agent_cmd_template)
        if not passed:
            print(f" [X] Agent reachable check failed: {message}")
            return False
        print(f" [✓] {message}")
        
        # Check 3: Tests exist and are collectible
        passed, message = check_tests_exist(self.verify_cmd)
        if not passed:
            print(f" [X] Tests exist check failed: {message}")
            return False
        print(f" [✓] {message}")

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

        # Safety Snapshot
        print(" [1/5] Stashing clean state...")
        run_shell("git stash push -m 'Orchestrator Safety Snapshot'", ignore_error=True)

        last_error = None

        # Escalation Protocol: Try each model in sequence
        for model_idx, model in enumerate(self.models):
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

            safe_prompt = shlex.quote(full_task)
            agent_cmd = self.agent_cmd_template.replace("{prompt}", safe_prompt).replace("{model}", model)

            print(f" [2/5] Unleashing Agent ({model}) [timeout: {self.agent_timeout}s]...")
            agent_success, agent_output, _ = run_shell(agent_cmd, ignore_error=True, timeout=self.agent_timeout)

            if not has_changes():
                print(" [X] Agent made NO changes to repository!")
                print("     This likely means the agent failed or couldn't understand the task.")
                last_error = "Agent produced no output changes. Check if task is clear or agent is working."

                print(" [!] Resetting to clean state for retry...")
                run_shell("git reset --hard HEAD", ignore_error=True)
                run_shell("git clean -fd", ignore_error=True)
                continue

            print(" [3/5] Changes detected:")
            print(get_diff_summary())

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
                    return True
                else:
                    print(f" [X] Commit failed: {truncate_error(commit_output)}")
                    run_shell("git stash drop", ignore_error=True)
                    return False
            else:
                print(" [X] FAILURE. Output snippet:")
                print(f"---\n{truncate_error(output)}...\n---")
                last_error = output

                print(" [!] Resetting to clean state for retry...")
                run_shell("git reset --hard HEAD", ignore_error=True)
                run_shell("git clean -fd", ignore_error=True)

        print(f"\n [!] Task failed after {len(self.models)} model(s). Reverting to start.")
        run_shell("git stash pop", ignore_error=True)
        return False

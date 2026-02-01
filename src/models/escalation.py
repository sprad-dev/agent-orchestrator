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
from src.shell import run_shell, has_changes, get_diff_summary, get_diff_content


DEFAULT_MODELS = ["claude-4.5-haiku", "claude-4.5-haiku", "claude-4.5-sonnet"]


class EscalationExecutor:
    """Executes tasks using model escalation on failure."""

    def __init__(self, agent_cmd_template, verify_cmd, models=None):
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.models = models if models else DEFAULT_MODELS

    def execute(self, task):
        """Execute task with escalation protocol."""
        print(f"--- SUPERVISOR STARTED ---")
        print(f"Target: {os.getcwd()}")
        print(f"Task: {task}")
        print(f"Escalation Chain: {' -> '.join(self.models)}")

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
{last_error[:1000] if last_error else "No error captured"}

Fix the error and implement correctly. Think step-by-step."""

                full_task = retry_prompt

            safe_prompt = shlex.quote(full_task)
            agent_cmd = self.agent_cmd_template.replace("{prompt}", safe_prompt).replace("{model}", model)

            print(f" [2/5] Unleashing Agent ({model})...")
            agent_success, agent_output, _ = run_shell(agent_cmd, ignore_error=True)

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
                    print(f" [X] Commit failed: {commit_output[:200]}")
                    run_shell("git stash drop", ignore_error=True)
                    return False
            else:
                print(" [X] FAILURE. Output snippet:")
                print(f"---\n{output[:300]}...\n---")
                last_error = output

                print(" [!] Resetting to clean state for retry...")
                run_shell("git reset --hard HEAD", ignore_error=True)
                run_shell("git clean -fd", ignore_error=True)

        print(f"\n [!] Task failed after {len(self.models)} model(s). Reverting to start.")
        run_shell("git stash pop", ignore_error=True)
        return False

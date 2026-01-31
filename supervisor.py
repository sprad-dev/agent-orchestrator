#!/usr/bin/env python3
import subprocess
import sys
import os
import argparse
import shlex

# --- DEFAULTS ---
# You can override these via CLI args later if needed
DEFAULT_AGENT = "claude {prompt}"
DEFAULT_VERIFIER = "pytest"
MAX_RETRIES = 3

class RalphLoop:
    def __init__(self, agent_cmd_template, verify_cmd, max_retries):
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.max_retries = max_retries

    def run_shell(self, cmd, ignore_error=False):
        """Runs a command in the CURRENT working directory."""
        print(f" [exec] {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                check=not ignore_error,
                capture_output=True,
                text=True
            )
            return True, result.stdout, result.returncode
        except subprocess.CalledProcessError as e:
            return False, e.stderr + e.stdout, e.returncode

    def has_changes(self):
        """Check if there are any uncommitted changes in the working directory."""
        success, output, _ = self.run_shell("git status --porcelain", ignore_error=True)
        return success and len(output.strip()) > 0

    def get_diff_summary(self):
        """Get a summary of changes made."""
        success, output, _ = self.run_shell("git diff --stat", ignore_error=True)
        return output if success else "Unable to get diff"

    def execute(self, task):
        print(f"--- 🕵️ SUPERVISOR STARTED ---")
        print(f"Target: {os.getcwd()}")
        print(f"Task: {task}")

        # 1. Safety Snapshot
        print(" [1/5] 💾 Stashing clean state...")
        self.run_shell("git stash push -m 'Orchestrator Safety Snapshot'", ignore_error=True)

        last_error = None

        for attempt in range(1, self.max_retries + 1):
            print(f"\n--- 🔄 ATTEMPT {attempt}/{self.max_retries} ---")

            # 2. Run Agent
            context = f". Fix previous error: {last_error}" if last_error else ""
            # Escape the prompt for shell safety
            safe_prompt = shlex.quote(f"{task} {context}")

            # Construct command (handling the format replacement manually for safety)
            # We replace only the {prompt} placeholder
            agent_cmd = self.agent_cmd_template.replace("{prompt}", safe_prompt)

            print(" [2/5] 🤖 Unleashing Agent...")
            agent_success, agent_output, _ = self.run_shell(agent_cmd, ignore_error=True)

            # Check if agent made any changes
            if not self.has_changes():
                print(" [X] ⚠️  Agent made NO changes to repository!")
                print("     This likely means the agent failed or couldn't understand the task.")
                last_error = "Agent produced no output changes. Check if task is clear or agent is working."

                # Reset and retry
                print(" [!] 🧹 Resetting to clean state for retry...")
                self.run_shell("git reset --hard HEAD", ignore_error=True)
                self.run_shell("git clean -fd", ignore_error=True)
                continue

            print(" [3/5] 📊 Changes detected:")
            print(self.get_diff_summary())

            # 3. Verify
            print(f" [4/5] ⚖️  Running Verifier: {self.verify_cmd}")
            passed, output, _ = self.run_shell(self.verify_cmd, ignore_error=True)

            if passed:
                print(" [5/5] ✅ SUCCESS! Verification passed.")
                # Commit the win
                commit_success, commit_output, _ = self.run_shell(
                    f"git add . && git commit -m 'Agent: {task}'",
                    ignore_error=True
                )

                if commit_success:
                    print("       ✓ Changes committed successfully")
                    return True
                else:
                    print(f" [X] ⚠️  Commit failed: {commit_output[:200]}")
                    return False
            else:
                print(" [X] 💥 FAILURE. Output snippet:")
                print(f"---\n{output[:300]}...\n---")
                last_error = output

                # 4. The Reset
                print(" [!] 🧹 Resetting to clean state for retry...")
                self.run_shell("git reset --hard HEAD", ignore_error=True)
                self.run_shell("git clean -fd", ignore_error=True)

        print(f"\n [!] ❌ Task failed after {self.max_retries} attempts. Reverting to start.")
        self.run_shell("git stash pop", ignore_error=True)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ralph Loop Supervisor")
    parser.add_argument("task", help="The coding task description")
    parser.add_argument("--verify", default=DEFAULT_VERIFIER, help="Command to verify success (default: pytest)")
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="Agent command template")
    
    args = parser.parse_args()
    
    loop = RalphLoop(args.agent, args.verify, MAX_RETRIES)
    loop.execute(args.task)

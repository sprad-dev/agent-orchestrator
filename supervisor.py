#!/usr/bin/env python3
import subprocess
import sys
import os
import argparse
import shlex
import json
import re
from pathlib import Path

# --- DEFAULTS ---
# You can override these via CLI args later if needed
DEFAULT_AGENT = "claude {prompt}"
DEFAULT_VERIFIER = "pytest"
MAX_RETRIES = 3
DEFAULT_MODELS = ["claude-3-haiku", "claude-3-haiku", "claude-3-5-sonnet"]

class RalphLoop:
    def __init__(self, agent_cmd_template, verify_cmd, max_retries, models=None):
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.max_retries = max_retries
        self.models = models if models else DEFAULT_MODELS

    def parse_context_files(self, task):
        """Parse context_files from task specification.
        
        Supports two formats:
        1. JSON-like: context_files: ["file1.py", "file2.py"]
        2. Inline marker: [context: file1.py, file2.py]
        
        Returns list of file paths or None if not specified.
        """
        # Try JSON-like format
        match = re.search(r'context_files:\s*\[([^\]]+)\]', task)
        if match:
            files_str = match.group(1)
            # Parse as JSON array or comma-separated
            try:
                files = json.loads('[' + files_str + ']')
                return [f.strip().strip('"\'') for f in files if f.strip()]
            except json.JSONDecodeError:
                # Fallback to comma-separated
                return [f.strip().strip('"\'') for f in files_str.split(',') if f.strip()]
        
        # Try inline marker format
        match = re.search(r'\[context:\s*([^\]]+)\]', task)
        if match:
            files_str = match.group(1)
            return [f.strip() for f in files_str.split(',') if f.strip()]
        
        return None

    def get_default_context_files(self, task):
        """Infer context files from task description.
        
        Looks for Python file mentions and includes corresponding test files.
        Returns list of file paths.
        """
        files = []
        
        # Find Python file mentions in task
        py_files = re.findall(r'\b(\w+\.py)\b', task)
        for f in py_files:
            if os.path.exists(f):
                files.append(f)
                # Add corresponding test file if it exists
                test_file = f'test_{f}'
                if os.path.exists(test_file):
                    files.append(test_file)
        
        return list(set(files))  # Remove duplicates

    def build_context(self, files):
        """Load specified files and build context string.
        
        Returns formatted context with file contents.
        """
        if not files:
            return ""
        
        context_parts = ["\n=== CONTEXT FILES ===\n"]
        
        for filepath in files:
            if not os.path.exists(filepath):
                context_parts.append(f"\n--- {filepath} (NOT FOUND) ---\n")
                continue
            
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                context_parts.append(f"\n--- {filepath} ---\n{content}\n")
            except Exception as e:
                context_parts.append(f"\n--- {filepath} (ERROR: {e}) ---\n")
        
        context_parts.append("=== END CONTEXT ===\n")
        return ''.join(context_parts)

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
            success = result.returncode == 0
            return success, result.stdout, result.returncode
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
        print(f"Escalation Chain: {' → '.join(self.models)}")

        # Parse context files from task
        context_files = self.parse_context_files(task)
        if context_files is None:
            # Use default context inference
            context_files = self.get_default_context_files(task)
        
        if context_files:
            print(f" [Context] 📁 Loading {len(context_files)} file(s): {', '.join(context_files)}")
        else:
            print(f" [Context] ⚠️  No context files specified or detected")

        # 1. Safety Snapshot
        print(" [1/5] 💾 Stashing clean state...")
        self.run_shell("git stash push -m 'Orchestrator Safety Snapshot'", ignore_error=True)

        last_error = None

        # Escalation Protocol: Try each model in sequence
        for model_idx, model in enumerate(self.models):
            attempt = model_idx + 1
            print(f"\n--- 🔄 ATTEMPT {attempt}/{len(self.models)} [Model: {model}] ---")

            # 2. Run Agent with context
            escalation_context = ""
            if last_error:
                escalation_context = f"\n\nPREVIOUS ATTEMPT FAILED with error:\n{last_error}\n\nThink step-by-step and fix this."
            
            # Build file context
            file_context = self.build_context(context_files)
            
            # Construct full prompt with context
            full_task = f"{file_context}\n{task}{escalation_context}"
            safe_prompt = shlex.quote(full_task)

            # Construct command with model substitution
            agent_cmd = self.agent_cmd_template.replace("{prompt}", safe_prompt).replace("{model}", model)

            print(f" [2/5] 🤖 Unleashing Agent ({model})...")
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
                print(f" [5/5] ✅ SUCCESS! Verification passed with {model}.")
                # Commit the win
                commit_success, commit_output, _ = self.run_shell(
                    f"git add . && git commit -m 'Agent ({model}): {task}'",
                    ignore_error=True
                )

                if commit_success:
                    print(f"       ✓ Changes committed successfully (solved by {model})")
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

        print(f"\n [!] ❌ Task failed after {len(self.models)} model(s). Reverting to start.")
        self.run_shell("git stash pop", ignore_error=True)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ralph Loop Supervisor")
    parser.add_argument("task", help="The coding task description")
    parser.add_argument("--verify", default=DEFAULT_VERIFIER, help="Command to verify success (default: pytest)")
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="Agent command template (use {model} for model substitution)")
    parser.add_argument("--models", help="Comma-separated list of models to try in escalation order (e.g., 'claude-3-haiku,claude-3-5-sonnet')")
    
    args = parser.parse_args()
    
    # Parse models list if provided
    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(',')]
    
    loop = RalphLoop(args.agent, args.verify, MAX_RETRIES, models=models)
    loop.execute(args.task)

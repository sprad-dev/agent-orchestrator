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
DEFAULT_MODELS = ["claude-4.5-haiku", "claude-4.5-haiku", "claude-4.5-sonnet"]

class RalphLoop:
    def __init__(self, agent_cmd_template, verify_cmd, max_retries, models=None, test_model=None, impl_model=None):
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.max_retries = max_retries
        self.models = models if models else DEFAULT_MODELS
        self.test_model = test_model
        self.impl_model = impl_model
        self.two_phase_mode = test_model is not None and impl_model is not None

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

    def run_test_generation_phase(self, task, context_files):
        """Phase 1: Generate tests using smart model."""
        print(f"\n=== 🧠 TEST GENERATION PHASE (Model: {self.test_model}) ===")
        
        # Build file context
        file_context = self.build_context(context_files)
        
        # Construct test generation prompt
        test_prompt = f"""{file_context}

TASK: Generate pytest test file(s) for the following requirement:
{task}

REQUIREMENTS:
- Write clear, comprehensive tests that will FAIL initially
- Tests should specify the exact behavior needed
- Use descriptive test names and assertions
- Create test files following pytest conventions (test_*.py)

Generate the test file(s) now."""
        
        safe_prompt = shlex.quote(test_prompt)
        agent_cmd = self.agent_cmd_template.replace("{prompt}", safe_prompt).replace("{model}", self.test_model)
        
        print(f" [1/3] 🧪 Generating tests with {self.test_model}...")
        agent_success, agent_output, _ = self.run_shell(agent_cmd, ignore_error=True)
        
        # Check if agent made any changes
        if not self.has_changes():
            print(" [X] ⚠️  Test generation produced NO changes!")
            return False
        
        print(" [2/3] 📊 Test files created:")
        print(self.get_diff_summary())
        
        # Commit test files
        print(" [3/3] 💾 Committing test files...")
        commit_success, commit_output, _ = self.run_shell(
            f"git add . && git commit -m 'Generated tests: {task[:50]}'",
            ignore_error=True
        )
        
        if not commit_success:
            print(f" [X] ⚠️  Failed to commit tests: {commit_output[:200]}")
            return False
        
        print(" ✅ Test generation complete!")
        return True

    def run_implementation_phase(self, task, context_files):
        """Phase 2: Implement code to pass tests using cheap model."""
        print(f"\n=== 🔨 IMPLEMENTATION PHASE (Model: {self.impl_model}) ===")
        
        # Run tests to get initial failure output
        print(" [1/4] 🧪 Running tests to capture initial failure...")
        test_passed, test_output, _ = self.run_shell(self.verify_cmd, ignore_error=True)
        
        if test_passed:
            print(" [!] ⚠️  Tests already pass - nothing to implement!")
            return True
        
        print(" [X] Tests failed (expected). Error output captured.")
        
        # Build file context including test files
        file_context = self.build_context(context_files)
        
        # Construct implementation prompt with test failure context
        impl_prompt = f"""{file_context}

TASK: Implement code to make the following tests pass:
{task}

TEST FAILURE OUTPUT:
{test_output[:2000]}

REQUIREMENTS:
- Write minimal code to make the tests pass
- Follow Red-Green-Refactor: make it work first
- Do not modify the test files
- Focus on passing the assertions

Implement the code now."""
        
        safe_prompt = shlex.quote(impl_prompt)
        agent_cmd = self.agent_cmd_template.replace("{prompt}", safe_prompt).replace("{model}", self.impl_model)
        
        print(f" [2/4] 🤖 Implementing with {self.impl_model}...")
        agent_success, agent_output, _ = self.run_shell(agent_cmd, ignore_error=True)
        
        # Check if agent made any changes
        if not self.has_changes():
            print(" [X] ⚠️  Implementation produced NO changes!")
            return False
        
        print(" [3/4] 📊 Changes detected:")
        print(self.get_diff_summary())
        
        # Verify implementation
        print(f" [4/4] ⚖️  Running tests to verify implementation...")
        test_passed, test_output, _ = self.run_shell(self.verify_cmd, ignore_error=True)
        
        if test_passed:
            print(" ✅ Implementation successful! Tests pass.")
            # Commit the implementation
            commit_success, commit_output, _ = self.run_shell(
                f"git add . && git commit -m 'Implemented: {task[:50]}'",
                ignore_error=True
            )
            return commit_success
        else:
            print(" [X] 💥 Tests still failing:")
            print(f"---\n{test_output[:300]}...\n---")
            return False

    def execute_two_phase(self, task):
        """Execute task using two-phase architect/intern approach."""
        print(f"--- 🕵️ SUPERVISOR STARTED (TWO-PHASE MODE) ---")
        print(f"Target: {os.getcwd()}")
        print(f"Task: {task}")
        print(f"Test Model: {self.test_model}")
        print(f"Implementation Model: {self.impl_model}")
        
        # Parse context files from task
        context_files = self.parse_context_files(task)
        if context_files is None:
            context_files = self.get_default_context_files(task)
        
        if context_files:
            print(f" [Context] 📁 Loading {len(context_files)} file(s): {', '.join(context_files)}")
        else:
            print(f" [Context] ⚠️  No context files specified or detected")
        
        # Safety snapshot
        print(" [Safety] 💾 Stashing clean state...")
        self.run_shell("git stash push -m 'Orchestrator Safety Snapshot'", ignore_error=True)
        
        # Phase 1: Test Generation
        if not self.run_test_generation_phase(task, context_files):
            print("\n [!] ❌ Test generation failed. Reverting...")
            self.run_shell("git reset --hard HEAD", ignore_error=True)
            self.run_shell("git stash pop", ignore_error=True)
            return False
        
        # Phase 2: Implementation
        if not self.run_implementation_phase(task, context_files):
            print("\n [!] ❌ Implementation failed. Reverting...")
            self.run_shell("git reset --hard HEAD~1", ignore_error=True)  # Remove both commits
            self.run_shell("git clean -fd", ignore_error=True)  # Clean untracked files
            self.run_shell("git stash pop", ignore_error=True)
            return False
        
        print("\n [!] ✅ TWO-PHASE EXECUTION COMPLETE!")
        return True

    def execute(self, task):
        # Route to two-phase mode if enabled
        if self.two_phase_mode:
            return self.execute_two_phase(task)
        
        # Original single-phase execution
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
    parser.add_argument("--test-model", help="Model to use for test generation phase (enables two-phase mode)")
    parser.add_argument("--impl-model", help="Model to use for implementation phase (enables two-phase mode)")
    
    args = parser.parse_args()
    
    # Parse models list if provided
    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(',')]
    
    loop = RalphLoop(args.agent, args.verify, MAX_RETRIES, models=models, 
                     test_model=args.test_model, impl_model=args.impl_model)
    loop.execute(args.task)

"""Two-phase (Architect/Intern) execution strategy.

This module implements the test-driven model selection pattern:
- Phase 1: Smart model (architect) writes tests
- Phase 2: Cheap model (intern) writes implementation

This optimizes cost by using expensive models only for design work.
"""

import os
import shlex

from src.context import build_static_context, parse_context_files, get_default_context_files
from src.shell import run_shell, has_changes, get_diff_summary
from src.preconditions import check_git_clean


class TwoPhaseExecutor:
    """Executes tasks using architect/intern model split."""

    def __init__(self, agent_cmd_template, verify_cmd, test_model, impl_model):
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.test_model = test_model
        self.impl_model = impl_model

    def run_test_generation_phase(self, task, context_files):
        """Phase 1: Generate tests using smart model."""
        print(f"\n=== TEST GENERATION PHASE (Model: {self.test_model}) ===")

        # Build static context optimized for caching
        static_context, context_size = build_static_context(context_files)
        print(f" [Cache] Static context: {context_size:,} bytes (cacheable)")

        # Construct test generation prompt with STATIC content first
        test_prompt = f"""{static_context}

=== SPECIFIC TASK (Dynamic) ===
Generate pytest test file(s) for the following requirement:
{task}

REQUIREMENTS:
- Write clear, comprehensive tests that will FAIL initially
- Tests should specify the exact behavior needed
- Use descriptive test names and assertions
- Create test files following pytest conventions (test_*.py)

Generate the test file(s) now."""

        safe_prompt = shlex.quote(test_prompt)
        agent_cmd = self.agent_cmd_template.replace("{prompt}", safe_prompt).replace("{model}", self.test_model)

        print(f" [1/3] Generating tests with {self.test_model}...")
        agent_success, agent_output, _ = run_shell(agent_cmd, ignore_error=True)

        if not has_changes():
            print(" [X] Test generation produced NO changes!")
            return False

        print(" [2/3] Test files created:")
        print(get_diff_summary())

        # Commit test files
        print(" [3/3] Committing test files...")
        safe_task = shlex.quote(f'Generated tests: {task[:50]}')
        commit_success, commit_output, _ = run_shell(
            f"git add . && git commit -m {safe_task}",
            ignore_error=True
        )

        if not commit_success:
            print(f" [X] Failed to commit tests: {commit_output[:200]}")
            return False

        print(" Test generation complete!")
        return True

    def run_implementation_phase(self, task, context_files):
        """Phase 2: Implement code to pass tests using cheap model."""
        print(f"\n=== IMPLEMENTATION PHASE (Model: {self.impl_model}) ===")

        # Run tests to get initial failure output
        print(" [1/4] Running tests to capture initial failure...")
        test_passed, test_output, _ = run_shell(self.verify_cmd, ignore_error=True)

        if test_passed:
            print(" [!] Tests already pass - nothing to implement!")
            return True

        print(" [X] Tests failed (expected). Error output captured.")

        # Build static context optimized for caching
        static_context, context_size = build_static_context(context_files)
        print(f" [Cache] Static context: {context_size:,} bytes (cacheable)")

        impl_prompt = f"""{static_context}

=== SPECIFIC TASK (Dynamic) ===
Implement code to make the following tests pass:
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

        print(f" [2/4] Implementing with {self.impl_model}...")
        agent_success, agent_output, _ = run_shell(agent_cmd, ignore_error=True)

        if not has_changes():
            print(" [X] Implementation produced NO changes!")
            return False

        print(" [3/4] Changes detected:")
        print(get_diff_summary())

        # Verify implementation
        print(f" [4/4] Running tests to verify implementation...")
        test_passed, test_output, _ = run_shell(self.verify_cmd, ignore_error=True)

        if test_passed:
            print(" Implementation successful! Tests pass.")
            safe_task = shlex.quote(f'Implemented: {task[:50]}')
            commit_success, commit_output, _ = run_shell(
                f"git add . && git commit -m {safe_task}",
                ignore_error=True
            )
            return commit_success
        else:
            print(" [X] Tests still failing:")
            print(f"---\n{test_output[:300]}...\n---")
            return False

    def execute(self, task):
        """Execute task using two-phase architect/intern approach."""
        print(f"--- SUPERVISOR STARTED (TWO-PHASE MODE) ---")
        print(f"Target: {os.getcwd()}")
        print(f"Task: {task}")
        print(f"Test Model: {self.test_model}")
        print(f"Implementation Model: {self.impl_model}")

        # Precondition: Check git working tree is clean
        passed, message = check_git_clean()
        if not passed:
            print(f"\n [X] PRECONDITION FAILED: {message}")
            print("     Commit or stash changes before running supervisor.")
            return False

        # Parse context files from task
        context_files = parse_context_files(task)
        if context_files is None:
            context_files = get_default_context_files(task)

        if context_files:
            print(f" [Context] Loading {len(context_files)} file(s): {', '.join(context_files)}")
        else:
            print(f" [Context] No context files specified or detected")

        # Safety snapshot
        print(" [Safety] Stashing clean state...")
        run_shell("git stash push -m 'Orchestrator Safety Snapshot'", ignore_error=True)

        # Phase 1: Test Generation
        if not self.run_test_generation_phase(task, context_files):
            print("\n [!] Test generation failed. Reverting...")
            run_shell("git reset --hard HEAD", ignore_error=True)
            run_shell("git stash pop", ignore_error=True)
            return False

        # Phase 2: Implementation
        if not self.run_implementation_phase(task, context_files):
            print("\n [!] Implementation failed. Reverting...")
            run_shell("git reset --hard HEAD~1", ignore_error=True)
            run_shell("git clean -fd", ignore_error=True)
            run_shell("git stash pop", ignore_error=True)
            return False

        print("\n [!] TWO-PHASE EXECUTION COMPLETE!")
        run_shell("git stash drop", ignore_error=True)
        return True

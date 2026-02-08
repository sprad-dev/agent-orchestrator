"""Three-phase (Architect/Intern/Adversary) execution strategy.

This module extends the two-phase model with adversarial test review:
- Phase 1: Smart model (architect) writes tests
- Phase 2: Cheap model (intern) writes implementation
- Phase 3: Adversary model reviews test quality and writes hardening tests
- Phase 4: Intern makes hardening tests pass

The adversary identifies:
- Tests that pass with hardcoded returns
- Mock-only assertions without real behavior validation
- Untested error paths
- Missing edge cases

This is automated mutation testing via adversarial prompting.
Cost: ~30-50% more tokens per task, but catches shallow coverage.
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
    truncate_error,
    build_agent_command,
)
from src.preconditions import check_git_clean, check_agent_reachable
from src.models.cost_tracker import AgentCostTracker, BudgetExceededException


DEFAULT_AGENT_TIMEOUT = 300  # 5 minutes
DEFAULT_EXECUTION_TIMEOUT = 1800  # 30 minutes total execution time


class ThreePhaseExecutor:
    """Executes tasks using architect/intern/adversary model split."""

    def __init__(
        self,
        agent_cmd_template: str,
        verify_cmd: str,
        test_model: str,
        impl_model: str,
        adversary_model: str,
        agent_timeout: int = DEFAULT_AGENT_TIMEOUT,
        execution_timeout: Optional[int] = DEFAULT_EXECUTION_TIMEOUT,
        max_cost_per_run: Optional[float] = None,
        max_tokens_per_run: Optional[int] = None
    ) -> None:
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.test_model = test_model
        self.impl_model = impl_model
        self.adversary_model = adversary_model
        self.agent_timeout = agent_timeout
        self.execution_timeout = execution_timeout
        self.max_cost_per_run = max_cost_per_run
        self.max_tokens_per_run = max_tokens_per_run
        self.start_time: Optional[float] = None
        self.cost_tracker: Optional[AgentCostTracker] = None

    def _check_timeout(self) -> bool:
        """Check if execution has exceeded timeout limit.

        Returns:
            True if timeout exceeded, False otherwise
        """
        if self.execution_timeout is None or self.start_time is None:
            return False

        elapsed = time.time() - self.start_time
        if elapsed >= self.execution_timeout:
            print(f"\n [!] EXECUTION TIMEOUT: {elapsed:.1f}s >= {self.execution_timeout}s")
            return True
        return False

    def _print_cost_summary(self) -> None:
        """Print execution cost summary."""
        if not self.cost_tracker or not self.start_time:
            return

        elapsed = time.time() - self.start_time
        summary = self.cost_tracker.get_run_summary()

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
        by_model = self.cost_tracker.get_cost_by_model()
        if by_model:
            print("\nCost by Model:")
            for model, cost in sorted(by_model.items(), key=lambda x: x[1], reverse=True):
                print(f"  {model}: ${cost:.4f}")

    def run_test_generation_phase(self, task: str, context_files: Optional[List[str]]) -> bool:
        """Phase 1: Generate tests using smart model."""
        print(f"\n=== PHASE 1: TEST GENERATION (Model: {self.test_model}) ===")

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

        agent_cmd = build_agent_command(self.agent_cmd_template, test_prompt, self.test_model)

        # Check timeout before running agent
        if self._check_timeout():
            print(" [!] Timeout before test generation agent call.")
            return False

        print(f" [1/3] Generating tests with {self.test_model} [timeout: {self.agent_timeout}s]...")
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
                cost_tracker=self.cost_tracker,
                model=self.test_model,
                phase="test_generation",
                attempt_num=1
            )
        except BudgetExceededException as e:
            print(f"\n [!] Budget exceeded during test generation: {str(e)}")
            return False

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
            print(f" [X] Failed to commit tests: {truncate_error(commit_output)}")
            return False

        print(" Test generation complete!")
        return True

    def run_implementation_phase(self, task: str, context_files: Optional[List[str]], phase_name: str = "IMPLEMENTATION") -> bool:
        """Phase 2 or 4: Implement code to pass tests using cheap model.

        Args:
            task: Original task description
            context_files: Context files to include
            phase_name: Display name for this phase ("IMPLEMENTATION" or "HARDENING")
        """
        print(f"\n=== PHASE {phase_name} (Model: {self.impl_model}) ===")

        # Run tests to get initial failure output
        print(" [1/4] Running tests to capture failure output...")
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
{truncate_error(test_output)}

REQUIREMENTS:
- Write minimal code to make the tests pass
- Follow Red-Green-Refactor: make it work first
- Do not modify the test files
- Focus on passing the assertions

Implement the code now."""

        agent_cmd = build_agent_command(self.agent_cmd_template, impl_prompt, self.impl_model)

        # Check timeout before running agent
        if self._check_timeout():
            print(" [!] Timeout before implementation agent call.")
            return False

        print(f" [2/4] Implementing with {self.impl_model} [timeout: {self.agent_timeout}s]...")
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
                cost_tracker=self.cost_tracker,
                model=self.impl_model,
                phase=phase_name.lower(),
                attempt_num=1
            )
        except BudgetExceededException as e:
            print(f"\n [!] Budget exceeded during {phase_name.lower()}: {str(e)}")
            return False

        if not has_changes():
            print(" [X] Implementation produced NO changes!")
            return False

        print(" [3/4] Changes detected:")
        print(get_diff_summary())

        # Check timeout before verification
        if self._check_timeout():
            print(" [!] Timeout before verification.")
            return False

        # Verify implementation
        print(f" [4/4] Running tests to verify implementation...")
        test_passed, test_output, _ = run_shell(self.verify_cmd, ignore_error=True)

        if test_passed:
            print(f" {phase_name} successful! Tests pass.")
            safe_task = shlex.quote(f'{phase_name}: {task[:50]}')
            commit_success, commit_output, _ = run_shell(
                f"git add . && git commit -m {safe_task}",
                ignore_error=True
            )
            return commit_success
        else:
            print(" [X] Tests still failing:")
            print(f"---\n{truncate_error(test_output)}...\n---")
            return False

    def run_adversarial_review_phase(self, task: str, context_files: Optional[List[str]]) -> bool:
        """Phase 3: Adversary reviews test quality and writes hardening tests."""
        print(f"\n=== PHASE 3: ADVERSARIAL REVIEW (Model: {self.adversary_model}) ===")

        # Get current test files
        print(" [1/4] Scanning for test files...")
        test_files_cmd = "find . -type f -name 'test_*.py' -o -name '*_test.py' | grep -v __pycache__ | head -20"
        test_files_success, test_files_output, _ = run_shell(test_files_cmd, ignore_error=True)

        if not test_files_success or not test_files_output.strip():
            print(" [X] No test files found to review!")
            return False

        test_files = test_files_output.strip().split('\n')
        print(f" [✓] Found {len(test_files)} test file(s)")

        # Read test file contents
        test_contents = []
        for test_file in test_files[:5]:  # Limit to first 5 files to avoid context overflow
            read_success, file_content, _ = run_shell(f"cat {shlex.quote(test_file)}", ignore_error=True)
            if read_success:
                test_contents.append(f"=== {test_file} ===\n{file_content}\n")

        if not test_contents:
            print(" [X] Could not read test files!")
            return False

        # Build static context optimized for caching
        static_context, context_size = build_static_context(context_files)
        print(f" [Cache] Static context: {context_size:,} bytes (cacheable)")

        # Construct adversarial review prompt
        adversary_prompt = f"""{static_context}

=== SPECIFIC TASK (Dynamic) ===
You are an ADVERSARIAL REVIEWER. Your job is to identify weaknesses in test coverage and write hardening tests.

ORIGINAL TASK:
{task}

EXISTING TEST FILES:
{''.join(test_contents)}

INSTRUCTIONS:
Review the existing tests for these common problems:
1. **Hardcoded returns**: Tests that pass with stub implementations (return 42, return "hello", etc.)
2. **Mock-only assertions**: Tests that only verify mocks were called, not actual behavior
3. **Untested error paths**: Missing tests for exceptions, edge cases, invalid inputs
4. **Missing edge cases**: No tests for empty inputs, boundary values, special characters, etc.

Your task:
- Identify at least 2-3 test quality issues in the existing tests
- Write NEW hardening test functions that would fail if the implementation cheats
- Add these tests to the appropriate test file(s)
- Use descriptive names like `test_not_hardcoded_return()`, `test_error_handling()`, etc.

Generate the hardening tests now. These tests should FAIL initially to prove the implementation isn't shallow."""

        agent_cmd = build_agent_command(self.agent_cmd_template, adversary_prompt, self.adversary_model)

        # Check timeout before running agent
        if self._check_timeout():
            print(" [!] Timeout before adversarial review agent call.")
            return False

        print(f" [2/4] Reviewing tests with {self.adversary_model} [timeout: {self.agent_timeout}s]...")
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
                cost_tracker=self.cost_tracker,
                model=self.adversary_model,
                phase="adversarial_review",
                attempt_num=1
            )
        except BudgetExceededException as e:
            print(f"\n [!] Budget exceeded during adversarial review: {str(e)}")
            return False

        if not has_changes():
            print(" [!] No hardening tests added - existing tests may be sufficient")
            return True  # Not a failure - maybe tests were already good

        print(" [3/4] Hardening tests added:")
        print(get_diff_summary())

        # Commit hardening tests
        print(" [4/4] Committing hardening tests...")
        safe_task = shlex.quote(f'Adversarial hardening tests: {task[:50]}')
        commit_success, commit_output, _ = run_shell(
            f"git add . && git commit -m {safe_task}",
            ignore_error=True
        )

        if not commit_success:
            print(f" [X] Failed to commit hardening tests: {truncate_error(commit_output)}")
            return False

        print(" Adversarial review complete!")
        return True

    def execute(self, task: str) -> bool:
        """Execute task using three-phase architect/intern/adversary approach."""
        self.start_time = time.time()

        # Initialize cost tracker
        self.cost_tracker = AgentCostTracker(
            max_cost_per_run=self.max_cost_per_run,
            max_tokens_per_run=self.max_tokens_per_run
        )
        self.cost_tracker.reset_run_budget()

        print(f"--- SUPERVISOR STARTED (THREE-PHASE MODE) ---")
        print(f"Target: {os.getcwd()}")
        print(f"Task: {task}")
        print(f"Architect Model: {self.test_model}")
        print(f"Intern Model: {self.impl_model}")
        print(f"Adversary Model: {self.adversary_model}")
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

        # Parse context files from task
        context_files = parse_context_files(task)
        if context_files is None:
            context_files = get_default_context_files(task)

        if context_files:
            print(f" [Context] Loading {len(context_files)} file(s): {', '.join(context_files)}")
        else:
            print(f" [Context] No context files specified or detected")

        # Check timeout after preconditions
        if self._check_timeout():
            print(" [!] Timeout during preconditions. Aborting.")
            return False

        # Safety snapshot
        print(" [Safety] Stashing clean state...")
        run_shell("git stash push -m 'Orchestrator Safety Snapshot'", ignore_error=True)

        # Phase 1: Test Generation
        if self._check_timeout():
            print("\n [!] Execution timeout exceeded before test generation. Aborting.")
            run_shell("git stash pop", ignore_error=True)
            return False

        if not self.run_test_generation_phase(task, context_files):
            print("\n [!] Test generation failed. Reverting...")
            run_shell("git reset --hard HEAD", ignore_error=True)
            run_shell("git stash pop", ignore_error=True)
            self._print_cost_summary()
            return False

        # Phase 2: Initial Implementation
        if self._check_timeout():
            print("\n [!] Execution timeout exceeded before implementation. Reverting...")
            self._revert_all_phases()
            return False

        if not self.run_implementation_phase(task, context_files, "2: INITIAL IMPLEMENTATION"):
            print("\n [!] Initial implementation failed. Reverting...")
            self._revert_all_phases()
            self._print_cost_summary()
            return False

        # Phase 3: Adversarial Review
        if self._check_timeout():
            print("\n [!] Execution timeout exceeded before adversarial review. Keeping initial implementation.")
            run_shell("git stash drop", ignore_error=True)
            self._print_cost_summary()
            return True  # Initial implementation succeeded, adversary is optional bonus

        if not self.run_adversarial_review_phase(task, context_files):
            print("\n [!] Adversarial review failed or produced no changes. Keeping initial implementation.")
            run_shell("git stash drop", ignore_error=True)
            self._print_cost_summary()
            return True  # Not a critical failure

        # Phase 4: Hardening Implementation
        if self._check_timeout():
            print("\n [!] Execution timeout exceeded before hardening. Reverting hardening tests.")
            run_shell("git reset --hard HEAD~1", ignore_error=True)  # Remove hardening tests
            run_shell("git stash drop", ignore_error=True)
            self._print_cost_summary()
            return True  # Initial implementation succeeded

        # Check if hardening tests actually need work
        test_passed, test_output, _ = run_shell(self.verify_cmd, ignore_error=True)
        if test_passed:
            print("\n [!] Hardening tests already pass - no additional work needed!")
            run_shell("git stash drop", ignore_error=True)
            self._print_cost_summary()
            return True

        if not self.run_implementation_phase(task, context_files, "4: HARDENING IMPLEMENTATION"):
            print("\n [!] Hardening implementation failed. Reverting hardening tests but keeping initial implementation.")
            run_shell("git reset --hard HEAD~1", ignore_error=True)  # Remove hardening tests
            run_shell("git stash drop", ignore_error=True)
            self._print_cost_summary()
            return True  # Initial implementation succeeded, hardening is optional

        print("\n [!] THREE-PHASE EXECUTION COMPLETE WITH HARDENING!")
        run_shell("git stash drop", ignore_error=True)
        self._print_cost_summary()
        return True

    def _revert_all_phases(self) -> None:
        """Revert all commits and restore clean state."""
        # Count commits since start (find the safety snapshot in reflog)
        result, output, _ = run_shell("git rev-list --count HEAD@{10.minutes.ago}..HEAD", ignore_error=True)
        if result:
            try:
                commit_count = int(output.strip())
                if commit_count > 0:
                    run_shell(f"git reset --hard HEAD~{commit_count}", ignore_error=True)
            except ValueError:
                # Fallback: reset to before any phases
                run_shell("git reset --hard HEAD~3", ignore_error=True)
        else:
            # Fallback: reset to before any phases
            run_shell("git reset --hard HEAD~3", ignore_error=True)

        run_shell("git clean -fd", ignore_error=True)
        run_shell("git stash pop", ignore_error=True)

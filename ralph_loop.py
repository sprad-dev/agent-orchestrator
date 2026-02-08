#!/usr/bin/env python3
"""Ralph Loop - Fresh context iteration for agent tasks.

Implements Huntley's Ralph Loop pattern:
- Spawn fresh agent with clean context
- Execute task using supervisor.py
- Check verification
- If incomplete: respawn with spec + git diff only
- Repeat until done or max iterations

Progress persists through artifacts (git, files), not agent memory.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _ensure_log_dir(iteration: int) -> Path:
    """Ensure .ralph_logs/iteration_N/ directory exists.

    Args:
        iteration: Iteration number (1-based)

    Returns:
        Path to the iteration log directory
    """
    log_dir = Path(".ralph_logs") / f"iteration_{iteration}"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def find_supervisor() -> str:
    """Find supervisor.py - check local directory first, then ralph_loop.py's directory.

    Returns:
        Path to supervisor.py (absolute if found in ralph_loop.py's dir, relative otherwise)
    """
    # Check current directory first
    if Path("./supervisor.py").exists():
        return "./supervisor.py"

    # Check ralph_loop.py's directory (agent-orchestrator project)
    ralph_dir = Path(__file__).resolve().parent
    supervisor_in_ralph_dir = ralph_dir / "supervisor.py"
    if supervisor_in_ralph_dir.exists():
        return str(supervisor_in_ralph_dir)

    # Fallback to relative path (will fail with clear error message)
    return "./supervisor.py"


class SpecTracker:
    """Track spec items and their completion status."""

    def __init__(self, spec_file: str = ".ralph_spec.json"):
        self.spec_file = Path(spec_file)
        self.items: List[Dict[str, any]] = []
        self._load()

    def _load(self) -> None:
        """Load spec from file if it exists."""
        if self.spec_file.exists():
            try:
                with open(self.spec_file, 'r') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self.items = data.get('items', [])
            except (json.JSONDecodeError, FileNotFoundError):
                # Empty or corrupted file, start fresh
                self.items = []

    def _save(self) -> None:
        """Save spec to file."""
        with open(self.spec_file, 'w') as f:
            json.dump({'items': self.items}, f, indent=2)

    def add_item(self, description: str, check_cmd: Optional[str] = None) -> None:
        """Add a spec item.

        Args:
            description: What needs to be done
            check_cmd: Optional command to verify completion
        """
        self.items.append({
            'description': description,
            'check_cmd': check_cmd,
            'completed': False
        })
        self._save()

    def check_all(self, default_check: str) -> Tuple[bool, List[str]]:
        """Check if all spec items are complete.

        Args:
            default_check: Default verification command if item has no check_cmd

        Returns:
            Tuple of (all_complete, failed_items)
        """
        failed = []

        for item in self.items:
            if item['completed']:
                continue

            check_cmd = item.get('check_cmd') or default_check
            result = subprocess.run(
                check_cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                item['completed'] = True
            else:
                failed.append(item['description'])

        self._save()
        all_complete = all(item['completed'] for item in self.items)
        return all_complete, failed

    def get_status(self) -> str:
        """Get human-readable status."""
        if not self.items:
            return "No spec items defined"

        completed = sum(1 for item in self.items if item['completed'])
        total = len(self.items)

        status = f"Spec: {completed}/{total} items complete\n"
        for i, item in enumerate(self.items, 1):
            check = "✓" if item['completed'] else "○"
            status += f"  {check} {i}. {item['description']}\n"

        return status


class RalphLoop:
    """Main Ralph Loop coordinator."""

    def __init__(
        self,
        task_description: str,
        verify_cmd: str = "pytest",
        max_iterations: int = 5,
        max_cost: Optional[float] = None,
        max_tokens: Optional[int] = None,
        supervisor_cmd: str = "./supervisor.py",
        agent_cmd: str = "claude -p --dangerously-skip-permissions --model {model} {prompt}",
        fallback_agents: Optional[List[str]] = None,
        diagnose: bool = False
    ):
        self.task_description = task_description
        self.verify_cmd = verify_cmd
        self.max_iterations = max_iterations
        self.max_cost = max_cost
        self.max_tokens = max_tokens
        self.supervisor_cmd = supervisor_cmd
        self.agent_cmd = agent_cmd
        self.fallback_agents = fallback_agents or []
        self.spec_tracker = SpecTracker()
        self.iteration = 0
        self.diagnose = diagnose
        self.iteration_summaries: List[Dict] = []

    def _get_git_diff(self) -> str:
        """Get current git diff for feedback."""
        result = subprocess.run(
            "git diff HEAD",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else ""

    def _get_git_status(self) -> str:
        """Get current git status for diagnostics."""
        result = subprocess.run(
            "git status --short",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else "(git status failed)"

    def _get_git_log_head(self, lines: int = 5) -> str:
        """Get recent git commit log for diagnostics."""
        result = subprocess.run(
            f"git log --oneline -n {lines} HEAD",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else "(git log failed)"

    def _get_changed_files(self) -> str:
        """Get list of changed files since HEAD."""
        result = subprocess.run(
            "git diff --name-only HEAD",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else "(no changes)"

    def _log_git_state(self, iteration: int, phase: str = "after") -> None:
        """Log git state to diagnostic file.

        Args:
            iteration: Current iteration number
            phase: "before" or "after" the iteration
        """
        if not self.diagnose:
            return

        log_dir = _ensure_log_dir(iteration)
        status_file = log_dir / f"git_status_{phase}.txt"

        status_content = f"=== Git Status ({phase}) ===\n\n"
        status_content += "## Changed Files\n"
        status_content += self._get_changed_files() + "\n"
        status_content += "\n## Git Status\n"
        status_content += self._get_git_status() + "\n"
        status_content += "\n## Recent Commits\n"
        status_content += self._get_git_log_head(3) + "\n"

        with open(status_file, 'w') as f:
            f.write(status_content)

    def _log_verification_output(self, iteration: int, test_result: bool, output: str = "") -> None:
        """Log verification/test output to diagnostic file.

        Args:
            iteration: Current iteration number
            test_result: Whether tests passed
            output: Verification command output
        """
        if not self.diagnose:
            return

        log_dir = _ensure_log_dir(iteration)
        verify_file = log_dir / "verification_output.txt"

        verify_content = f"=== Verification Results ===\n\n"
        verify_content += f"Status: {'PASSED' if test_result else 'FAILED'}\n"
        verify_content += f"Command: {self.verify_cmd}\n\n"
        verify_content += "=== Output ===\n"
        verify_content += output if output else "(no output captured)"

        with open(verify_file, 'w') as f:
            f.write(verify_content)

    def _run_supervisor(self, prompt: str) -> Tuple[bool, str]:
        """Run supervisor.py with the given prompt, trying fallbacks if primary fails.

        Args:
            prompt: Task prompt to send to supervisor

        Returns:
            Tuple of (success, output)
        """
        # Write prompt to log for reproducibility
        log_dir = _ensure_log_dir(self.iteration)
        prompt_file = log_dir / "prompt.txt"
        with open(prompt_file, 'w') as f:
            f.write(prompt)

        # Build list of agents to try (primary + fallbacks)
        agents_to_try = [self.agent_cmd] + self.fallback_agents

        last_output = ""

        for agent_idx, agent_cmd in enumerate(agents_to_try):
            is_fallback = agent_idx > 0
            agent_label = f"Fallback {agent_idx}" if is_fallback else "Primary"

            if is_fallback:
                print(f"\n [!] Primary agent failed, trying fallback: {agent_cmd}")

            # Build supervisor command
            cmd_parts = [self.supervisor_cmd, prompt]

            if self.max_cost:
                cmd_parts.extend(['--max-cost', str(self.max_cost)])

            if self.max_tokens:
                cmd_parts.extend(['--max-tokens', str(self.max_tokens)])

            # Add verify command
            cmd_parts.extend(['--verify', self.verify_cmd])

            # Add agent command
            cmd_parts.extend(['--agent', agent_cmd])

            cmd = ' '.join(shlex.quote(part) for part in cmd_parts)

            print(f"\n [exec] ({agent_label}) {cmd}")

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            stdout_output = result.stdout
            stderr_output = result.stderr
            output = stdout_output + stderr_output
            last_output = output

            # Write agent output to log files (always write both for consistent observability)
            output_file = log_dir / "agent_output.txt"
            error_file = log_dir / "agent_errors.txt"

            with open(output_file, 'w') as f:
                f.write(stdout_output)

            with open(error_file, 'w') as f:
                f.write(stderr_output)

            # Log agent command for reproducibility (diagnose mode)
            if self.diagnose:
                agent_cmd_file = log_dir / "agent_command.txt"
                with open(agent_cmd_file, 'w') as f:
                    f.write(f"Agent: {agent_label}\n")
                    f.write(f"Command: {cmd}\n")
                    f.write(f"Return Code: {result.returncode}\n")

            if result.returncode == 0:
                if is_fallback:
                    print(f" [✓] Fallback agent succeeded: {agent_cmd}")
                return True, output

            # Check if failure was due to budget/rate limit (should try fallback)
            if any(indicator in output.lower() for indicator in [
                'rate limit', 'usage limit', 'quota exceeded',
                'budget exceeded', '429', 'too many requests'
            ]):
                print(f" [X] {agent_label} hit limit, trying next agent...")
                continue
            else:
                # Other failure (verification, etc.) - don't try fallback
                print(f" [X] {agent_label} failed (not a limit issue)")
                return False, output

        print(f" [X] All agents exhausted ({len(agents_to_try)} tried)")
        return False, last_output

    def _build_initial_prompt(self) -> str:
        """Build prompt for first iteration."""
        return f"""TASK: {self.task_description}

This is iteration 1 of a Ralph Loop. Your goal is to complete the task above.

Focus on:
1. Understanding the requirements
2. Writing or generating tests (if needed)
3. Implementing the solution
4. Ensuring all tests pass

Work incrementally and commit your changes."""

    def _build_retry_prompt(self, failed_items: List[str]) -> str:
        """Build prompt for retry iteration.

        Args:
            failed_items: List of spec items that failed

        Returns:
            Retry prompt with minimal context
        """
        diff = self._get_git_diff()

        return f"""RETRY - Iteration {self.iteration}/{self.max_iterations}

ORIGINAL TASK:
{self.task_description}

PREVIOUS ATTEMPT STATUS:
{chr(10).join(f'  ✗ {item}' for item in failed_items)}

CODE CHANGES FROM LAST ATTEMPT (git diff):
{diff if diff else '(No changes were made)'}

INSTRUCTIONS:
Fix the issues and complete the remaining spec items. This is a fresh context -
progress persists through git commits, not conversation history.

Focus on making the verification pass."""

    @staticmethod
    def _ensure_gitignore_entry(pattern: str) -> None:
        """Ensure a pattern is in .gitignore so it doesn't dirty the working tree.

        Commits the change so the tree stays clean for precondition checks.
        """
        gitignore = Path(".gitignore")
        if gitignore.exists():
            content = gitignore.read_text()
            if pattern in content.splitlines():
                return
            # Ensure existing content ends with newline before appending
            prefix = "" if content.endswith('\n') else "\n"
        else:
            prefix = ""
        with open(gitignore, 'a') as f:
            f.write(f"{prefix}{pattern}\n")
        subprocess.run(
            ["git", "add", ".gitignore"],
            capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"chore: add {pattern} to .gitignore"],
            capture_output=True
        )

    def run(self) -> bool:
        """Run the Ralph Loop.

        Returns:
            True if task completed successfully, False otherwise
        """
        # Ensure .ralph_logs/ won't dirty the working tree
        self._ensure_gitignore_entry(".ralph_logs/")

        print("=== RALPH LOOP STARTED ===")
        print(f"Task: {self.task_description}")
        print(f"Max Iterations: {self.max_iterations}")
        print(f"Primary Agent: {self.agent_cmd}")
        if self.fallback_agents:
            print(f"Fallback Agents: {', '.join(self.fallback_agents)}")
        if self.max_cost:
            print(f"Cost Budget: ${self.max_cost}")
        if self.max_tokens:
            print(f"Token Budget: {self.max_tokens:,}")
        print()

        start_time = time.time()

        for self.iteration in range(1, self.max_iterations + 1):
            print(f"\n{'='*60}")
            print(f"ITERATION {self.iteration}/{self.max_iterations}")
            print(f"{'='*60}")

            # Build prompt based on iteration
            if self.iteration == 1:
                prompt = self._build_initial_prompt()
            else:
                # Check what failed
                all_complete, failed_items = self.spec_tracker.check_all(self.verify_cmd)

                if all_complete:
                    print("\n✓ All spec items complete!")
                    break

                print(f"\nRetry needed. {len(failed_items)} item(s) still failing:")
                for item in failed_items:
                    print(f"  ✗ {item}")

                prompt = self._build_retry_prompt(failed_items)

            # Run supervisor with fresh context
            success, output = self._run_supervisor(prompt)

            # Check if complete
            all_complete, failed_items = self.spec_tracker.check_all(self.verify_cmd)

            if all_complete:
                elapsed = time.time() - start_time
                print(f"\n{'='*60}")
                print("✓ RALPH LOOP COMPLETE!")
                print(f"  Iterations: {self.iteration}/{self.max_iterations}")
                print(f"  Duration: {elapsed:.1f}s")
                print(f"{'='*60}")
                return True

            # Show progress
            print(f"\n{self.spec_tracker.get_status()}")

        # Max iterations reached
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print("✗ RALPH LOOP FAILED")
        print(f"  Max iterations ({self.max_iterations}) reached")
        print(f"  Duration: {elapsed:.1f}s")
        print(f"\n{self.spec_tracker.get_status()}")
        print(f"{'='*60}")
        return False

    def print_diagnostic_summary(self) -> None:
        """Print diagnostic summary of all iterations.

        Reads from .ralph_logs/ and displays:
        - Summary of all iterations (converged/failed/no-progress)
        - File changes per iteration
        - Test results per iteration
        - Git state per iteration
        - Any error messages or warnings
        """
        logs_dir = Path(".ralph_logs")
        if not logs_dir.exists():
            print("\n[!] No diagnostic logs found (.ralph_logs/ directory does not exist)")
            return

        print("\n" + "="*70)
        print("DIAGNOSTIC SUMMARY")
        print("="*70)

        # Find all iteration directories
        iteration_dirs = sorted([d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith("iteration_")])

        if not iteration_dirs:
            print("[!] No iteration directories found in .ralph_logs/")
            return

        for iter_dir in iteration_dirs:
            iteration_num = iter_dir.name.split("_")[1]
            print(f"\n--- ITERATION {iteration_num} ---")

            # Read prompt
            prompt_file = iter_dir / "prompt.txt"
            if prompt_file.exists():
                prompt_content = prompt_file.read_text()
                # Show first line of prompt (usually indicates initial vs retry)
                first_line = prompt_content.split('\n')[0]
                print(f"  Prompt: {first_line[:80]}")

            # Read agent command info
            agent_cmd_file = iter_dir / "agent_command.txt"
            if agent_cmd_file.exists():
                agent_content = agent_cmd_file.read_text()
                lines = agent_content.split('\n')
                for line in lines:
                    if line.startswith("Agent:") or line.startswith("Return Code:"):
                        print(f"  {line}")

            # Read git status before/after
            git_status_after = iter_dir / "git_status_after.txt"

            if git_status_after.exists():
                git_content = git_status_after.read_text()
                # Extract changed files section
                in_changed_section = False
                for line in git_content.split('\n'):
                    if "## Changed Files" in line:
                        in_changed_section = True
                        continue
                    if in_changed_section and line.startswith("##"):
                        break
                    if in_changed_section and line.strip() and not line.startswith("#"):
                        print(f"  File change: {line.strip()}")

            # Read verification results
            verify_file = iter_dir / "verification_output.txt"
            if verify_file.exists():
                verify_content = verify_file.read_text()
                # Extract status line
                for line in verify_content.split('\n'):
                    if line.startswith("Status:"):
                        print(f"  Verification: {line}")

            # Read any error output
            error_file = iter_dir / "agent_errors.txt"
            if error_file.exists():
                error_content = error_file.read_text().strip()
                if error_content:
                    # Show first error line and line count
                    error_lines = error_content.split('\n')
                    first_error = error_lines[0][:100]
                    print(f"  Errors: {first_error}")
                    if len(error_lines) > 1:
                        print(f"           ({len(error_lines)} total error lines)")

        # Summary statistics
        print("\n" + "-"*70)
        print("SUMMARY STATISTICS")
        print("-"*70)
        print(f"Total iterations logged: {len(iteration_dirs)}")
        print(f"Max iterations configured: {self.max_iterations}")

        # Count successes
        successful_verifications = 0
        failed_verifications = 0

        for iter_dir in iteration_dirs:
            verify_file = iter_dir / "verification_output.txt"
            if verify_file.exists():
                content = verify_file.read_text()
                if "Status: PASSED" in content:
                    successful_verifications += 1
                elif "Status: FAILED" in content:
                    failed_verifications += 1

        print(f"Passed verifications: {successful_verifications}")
        print(f"Failed verifications: {failed_verifications}")

        # Show logs directory location
        print(f"\nDetailed logs available in: {logs_dir.resolve()}")
        print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Ralph Loop - Fresh context iteration for agent tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  ./ralph_loop.py "Add user authentication"

  # With budget limits
  ./ralph_loop.py "Fix bug in checkout" --max-cost 0.50 --max-iterations 3

  # Custom verification
  ./ralph_loop.py "Refactor API" --verify "pytest tests/api/"

  # With GitHub Copilot CLI as fallback
  ./ralph_loop.py "Implement feature X" \\
    --fallback-agents "gh copilot suggest -t shell {prompt}"

  # Multiple fallbacks (Copilot, then Aider)
  ./ralph_loop.py "Fix bug Y" \\
    --agent "claude {prompt}" \\
    --fallback-agents "gh copilot suggest -t shell {prompt},aider --yes {prompt}"
        """
    )

    parser.add_argument(
        "task",
        help="Task description for the agent"
    )
    parser.add_argument(
        "--verify",
        default="pytest",
        help="Verification command (default: pytest)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum loop iterations (default: 5)"
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        help="Maximum cost per iteration in USD"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        help="Maximum tokens per iteration"
    )
    parser.add_argument(
        "--supervisor",
        default=None,
        help="Path to supervisor.py (default: auto-detect from current dir or ralph_loop.py's dir)"
    )
    parser.add_argument(
        "--agent",
        default="claude -p --dangerously-skip-permissions --model {model} {prompt}",
        help="Primary agent command template (default: 'claude -p --dangerously-skip-permissions --model {model} {prompt}')"
    )
    parser.add_argument(
        "--fallback-agents",
        help="Comma-separated fallback agent commands (e.g., 'gh copilot suggest {prompt},aider {prompt}')"
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Enable diagnostic mode: logs detailed iteration info and prints summary at end"
    )

    args = parser.parse_args()

    # Parse fallback agents
    fallback_agents = None
    if args.fallback_agents:
        fallback_agents = [agent.strip() for agent in args.fallback_agents.split(',')]

    # Auto-detect supervisor path if not specified
    supervisor_path = args.supervisor if args.supervisor else find_supervisor()

    loop = RalphLoop(
        task_description=args.task,
        verify_cmd=args.verify,
        max_iterations=args.max_iterations,
        max_cost=args.max_cost,
        max_tokens=args.max_tokens,
        supervisor_cmd=supervisor_path,
        agent_cmd=args.agent,
        fallback_agents=fallback_agents,
        diagnose=args.diagnose
    )

    success = loop.run()

    # Display diagnostic summary if --diagnose flag was set
    if args.diagnose:
        loop.print_diagnostic_summary()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

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
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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
        supervisor_cmd: str = "./supervisor.py"
    ):
        self.task_description = task_description
        self.verify_cmd = verify_cmd
        self.max_iterations = max_iterations
        self.max_cost = max_cost
        self.max_tokens = max_tokens
        self.supervisor_cmd = supervisor_cmd
        self.spec_tracker = SpecTracker()
        self.iteration = 0

    def _get_git_diff(self) -> str:
        """Get current git diff for feedback."""
        result = subprocess.run(
            "git diff HEAD",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else ""

    def _run_supervisor(self, prompt: str) -> Tuple[bool, str]:
        """Run supervisor.py with the given prompt.

        Args:
            prompt: Task prompt to send to supervisor

        Returns:
            Tuple of (success, output)
        """
        # Build supervisor command
        cmd_parts = [self.supervisor_cmd, prompt]

        if self.max_cost:
            cmd_parts.extend(['--max-cost', str(self.max_cost)])

        if self.max_tokens:
            cmd_parts.extend(['--max-tokens', str(self.max_tokens)])

        # Add verify command
        cmd_parts.extend(['--verify', self.verify_cmd])

        cmd = ' '.join(f"'{part}'" if ' ' in part else part for part in cmd_parts)

        print(f"\n [exec] {cmd}")

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )

        output = result.stdout + result.stderr
        return result.returncode == 0, output

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

    def run(self) -> bool:
        """Run the Ralph Loop.

        Returns:
            True if task completed successfully, False otherwise
        """
        print("=== RALPH LOOP STARTED ===")
        print(f"Task: {self.task_description}")
        print(f"Max Iterations: {self.max_iterations}")
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
        default="./supervisor.py",
        help="Path to supervisor.py (default: ./supervisor.py)"
    )

    args = parser.parse_args()

    loop = RalphLoop(
        task_description=args.task,
        verify_cmd=args.verify,
        max_iterations=args.max_iterations,
        max_cost=args.max_cost,
        max_tokens=args.max_tokens,
        supervisor_cmd=args.supervisor
    )

    success = loop.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

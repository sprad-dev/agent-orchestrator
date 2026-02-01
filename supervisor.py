#!/usr/bin/env python3
"""Ralph Loop Supervisor - Thin orchestrator.

This is the main entry point that delegates to modular components:
- src/context/: Context file parsing and building
- src/shell/: Shell execution and git utilities
- src/models/: Execution strategies (escalation, two-phase)
- src/preconditions/: Pre-execution safety checks
- src/verification/: Multi-layer verification pipeline
- src/guards/: Commit safety guards
"""

import argparse

from src.models import EscalationExecutor, TwoPhaseExecutor
from src.shell import run_shell, has_changes, get_diff_summary, get_diff_content
from src.context import parse_context_files, get_default_context_files, build_static_context

# --- DEFAULTS ---
DEFAULT_AGENT = "claude {prompt}"
DEFAULT_VERIFIER = "pytest"
MAX_RETRIES = 3
DEFAULT_MODELS = ["claude-4.5-haiku", "claude-4.5-haiku", "claude-4.5-sonnet"]


class RalphLoop:
    """Main orchestrator that delegates to execution strategies."""

    def __init__(self, agent_cmd_template, verify_cmd, max_retries,
                 models=None, test_model=None, impl_model=None):
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.max_retries = max_retries
        self.models = models if models else DEFAULT_MODELS
        self.test_model = test_model
        self.impl_model = impl_model
        self.two_phase_mode = test_model is not None and impl_model is not None

        # Initialize the appropriate executor
        if self.two_phase_mode:
            self.executor = TwoPhaseExecutor(
                agent_cmd_template, verify_cmd, test_model, impl_model
            )
        else:
            self.executor = EscalationExecutor(
                agent_cmd_template, verify_cmd, self.models
            )

    def execute(self, task):
        """Execute task using configured strategy."""
        return self.executor.execute(task)

    # --- Backwards-compatible proxies for tests ---
    # These delegate to extracted modules while maintaining API compatibility

    def run_shell(self, cmd, ignore_error=False):
        """Proxy to src.shell.run_shell for backwards compatibility."""
        return run_shell(cmd, ignore_error)

    def has_changes(self):
        """Proxy to src.shell.has_changes for backwards compatibility."""
        return has_changes()

    def get_diff_summary(self):
        """Proxy to src.shell.get_diff_summary for backwards compatibility."""
        return get_diff_summary()

    def get_diff_content(self):
        """Proxy to src.shell.get_diff_content for backwards compatibility."""
        return get_diff_content()

    def parse_context_files(self, task):
        """Proxy to src.context.parse_context_files for backwards compatibility."""
        return parse_context_files(task)

    def get_default_context_files(self, task):
        """Proxy to src.context.get_default_context_files for backwards compatibility."""
        return get_default_context_files(task)

    def build_static_context(self, context_files):
        """Proxy to src.context.build_static_context for backwards compatibility."""
        return build_static_context(context_files)

    def execute_two_phase(self, task):
        """Proxy to TwoPhaseExecutor.execute for backwards compatibility."""
        if isinstance(self.executor, TwoPhaseExecutor):
            return self.executor.execute(task)
        # Create a temporary two-phase executor if not in two-phase mode
        temp_executor = TwoPhaseExecutor(
            self.agent_cmd_template, self.verify_cmd,
            self.test_model or "claude-4.5-sonnet",
            self.impl_model or "claude-4.5-haiku"
        )
        return temp_executor.execute(task)

    def run_test_generation_phase(self, task, context_files):
        """Proxy to TwoPhaseExecutor for backwards compatibility."""
        if isinstance(self.executor, TwoPhaseExecutor):
            return self.executor.run_test_generation_phase(task, context_files)
        return False

    def run_implementation_phase(self, task, context_files):
        """Proxy to TwoPhaseExecutor for backwards compatibility."""
        if isinstance(self.executor, TwoPhaseExecutor):
            return self.executor.run_implementation_phase(task, context_files)
        return False


def main():
    parser = argparse.ArgumentParser(description="Ralph Loop Supervisor")
    parser.add_argument("task", help="The coding task description")
    parser.add_argument("--verify", default=DEFAULT_VERIFIER,
                        help="Command to verify success (default: pytest)")
    parser.add_argument("--agent", default=DEFAULT_AGENT,
                        help="Agent command template (use {model} for model substitution)")
    parser.add_argument("--models",
                        help="Comma-separated list of models for escalation")
    parser.add_argument("--test-model",
                        help="Model for test generation (enables two-phase mode)")
    parser.add_argument("--impl-model",
                        help="Model for implementation (enables two-phase mode)")

    args = parser.parse_args()

    # Parse models list if provided
    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(',')]

    loop = RalphLoop(
        args.agent, args.verify, MAX_RETRIES,
        models=models,
        test_model=args.test_model,
        impl_model=args.impl_model
    )
    loop.execute(args.task)


if __name__ == "__main__":
    main()

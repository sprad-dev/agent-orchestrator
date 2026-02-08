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
import os
import sys
import warnings
import yaml
from pathlib import Path

# Add supervisor.py's parent directory to sys.path so imports work
# regardless of where this script is invoked from
SUPERVISOR_DIR = Path(__file__).resolve().parent
if str(SUPERVISOR_DIR) not in sys.path:
    sys.path.insert(0, str(SUPERVISOR_DIR))

from src.models import EscalationExecutor, TwoPhaseExecutor, ThreePhaseExecutor
from src.shell import run_shell, has_changes, get_diff_summary, get_diff_content
from src.context import parse_context_files, get_default_context_files, build_static_context

# --- DEFAULTS ---
DEFAULT_AGENT = "claude -p --dangerously-skip-permissions --model {model} {prompt}"
DEFAULT_VERIFIER = "pytest"
MAX_RETRIES = 3
DEFAULT_MODELS = ["claude-4.5-haiku", "claude-4.5-haiku", "claude-4.5-sonnet"]


def load_config(config_path: str = None) -> dict:
    """Load agent configuration from YAML file.
    
    Args:
        config_path: Path to config file. Defaults to agent.yaml in cwd.
    
    Returns:
        Parsed config as dict, or empty dict if not found/invalid.
    """
    if config_path is None:
        config_path = os.path.join(os.getcwd(), "agent.yaml")
    
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            if config is None:
                return {}
            # Validate YAML structure is a dict, not a list or scalar
            if not isinstance(config, dict):
                warnings.warn(
                    f"Config file {config_path} must be a YAML dict/object, "
                    f"not {type(config).__name__}. Ignoring config."
                )
                return {}
            return config
    except yaml.YAMLError as e:
        warnings.warn(f"Failed to parse YAML config at {config_path}: {e}")
        return {}


def validate_config(config: dict) -> list:
    """Validate loaded configuration and return list of warnings.
    
    Does NOT raise exceptions - only returns warnings. This allows
    graceful degradation and helpful debugging.
    
    Args:
        config: Loaded configuration dict.
    
    Returns:
        List of warning strings. Empty list if config is valid.
    """
    warnings_list = []
    
    if not config:
        return warnings_list
    
    # Known valid keys
    valid_keys = {
        'verify_cmd', 'agent_cmd', 'models', 'test_model', 'impl_model',
        'adversary_model', 'max_cost', 'max_tokens'
    }
    
    # Check for unknown keys
    unknown_keys = set(config.keys()) - valid_keys
    if unknown_keys:
        warnings_list.append(
            f"Unknown config keys will be ignored: {', '.join(sorted(unknown_keys))}"
        )
    
    # Validate agent_cmd contains {prompt} placeholder if present
    if 'agent_cmd' in config and config['agent_cmd']:
        agent_cmd = config['agent_cmd']
        if not isinstance(agent_cmd, str):
            warnings_list.append(
                f"agent_cmd must be a string, got {type(agent_cmd).__name__}"
            )
        elif '{prompt}' not in agent_cmd:
            warnings_list.append(
                "agent_cmd must contain '{prompt}' placeholder for task injection"
            )
    
    # Validate verify_cmd is a string if present
    if 'verify_cmd' in config and config['verify_cmd']:
        verify_cmd = config['verify_cmd']
        if not isinstance(verify_cmd, str):
            warnings_list.append(
                f"verify_cmd must be a string, got {type(verify_cmd).__name__}"
            )
        elif not verify_cmd.strip():
            warnings_list.append("verify_cmd is an empty string")
    
    # Validate models is a list if present
    if 'models' in config and config['models']:
        models = config['models']
        if not isinstance(models, list):
            warnings_list.append(
                f"models must be a list, got {type(models).__name__}"
            )
        elif not all(isinstance(m, str) for m in models):
            warnings_list.append("All items in models must be strings")
    
    return warnings_list



class RalphLoop:
    """Main orchestrator that delegates to execution strategies."""

    def __init__(self, agent_cmd_template, verify_cmd, max_retries,
                 models=None, test_model=None, impl_model=None, adversary_model=None,
                 max_cost_per_run=None, max_tokens_per_run=None):
        self.agent_cmd_template = agent_cmd_template
        self.verify_cmd = verify_cmd
        self.max_retries = max_retries
        self.models = models if models else DEFAULT_MODELS
        self.test_model = test_model
        self.impl_model = impl_model
        self.adversary_model = adversary_model
        self.max_cost_per_run = max_cost_per_run
        self.max_tokens_per_run = max_tokens_per_run

        # Determine execution mode
        self.three_phase_mode = (test_model is not None and
                                 impl_model is not None and
                                 adversary_model is not None)
        self.two_phase_mode = (test_model is not None and
                               impl_model is not None and
                               adversary_model is None)

        # Initialize the appropriate executor
        if self.three_phase_mode:
            self.executor = ThreePhaseExecutor(
                agent_cmd_template, verify_cmd, test_model, impl_model, adversary_model,
                max_cost_per_run=max_cost_per_run,
                max_tokens_per_run=max_tokens_per_run
            )
        elif self.two_phase_mode:
            self.executor = TwoPhaseExecutor(
                agent_cmd_template, verify_cmd, test_model, impl_model,
                max_cost_per_run=max_cost_per_run,
                max_tokens_per_run=max_tokens_per_run
            )
        else:
            self.executor = EscalationExecutor(
                agent_cmd_template, verify_cmd, self.models,
                max_cost_per_run=max_cost_per_run,
                max_tokens_per_run=max_tokens_per_run
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
    parser.add_argument("task", nargs='?', help="The coding task description")
    parser.add_argument("--verify", default=None,
                        help="Command to verify success (default: pytest)")
    parser.add_argument("--agent", default=None,
                        help="Agent command template (use {model} for model substitution)")
    parser.add_argument("--models",
                        help="Comma-separated list of models for escalation")
    parser.add_argument("--test-model",
                        help="Model for test generation (enables two-phase mode)")
    parser.add_argument("--impl-model",
                        help="Model for implementation (enables two-phase mode)")
    parser.add_argument("--adversary-model",
                        help="Model for adversarial review (enables three-phase mode, requires --test-model and --impl-model)")
    parser.add_argument("--max-cost", type=float,
                        help="Maximum cost per run in USD (e.g., 1.00)")
    parser.add_argument("--max-tokens", type=int,
                        help="Maximum tokens per run (e.g., 100000)")
    parser.add_argument("--self-check", action="store_true",
                        help="Run verification pipeline against own codebase (dogfood mode)")
    parser.add_argument("--self-check-ref", default="HEAD~1",
                        help="Git ref to diff against for --self-check (default: HEAD~1)")
    parser.add_argument("--adversarial", action="store_true",
                        help="Enable L7 LLM adversarial review during --self-check")
    parser.add_argument("--stats", action="store_true",
                        help="Show execution statistics and exit")
    parser.add_argument("--stats-days", type=int,
                        help="Number of days to include in stats (default: all time)")
    parser.add_argument("--show-config", action="store_true",
                        help="Show resolved configuration and exit")

    args = parser.parse_args()
    
    # Load configuration from agent.yaml
    config = load_config()
    
    # Validate config and print warnings
    config_warnings = validate_config(config)
    for warning in config_warnings:
        warnings.warn(warning)
    
    # Helper function to determine config source
    def get_source(cli_value, config_key):
        if cli_value is not None:
            return "CLI"
        elif config_key in config and config[config_key]:
            return "config"
        else:
            return "default"
    
    # Implement config priority: CLI Args > agent.yaml > Hardcoded Defaults
    verify_cmd = args.verify or config.get('verify_cmd') or DEFAULT_VERIFIER
    agent_template = args.agent or config.get('agent_cmd') or DEFAULT_AGENT
    
    # Parse models with priority: CLI > config > defaults
    if args.models:
        models = [m.strip() for m in args.models.split(',')]
    elif 'models' in config and config['models']:
        models = config['models']
    else:
        models = None  # Will default in RalphLoop
    
    # Handle --show-config flag
    if args.show_config:
        print("=== Resolved Configuration ===")
        print(f"verify_cmd: {verify_cmd} (source: {get_source(args.verify, 'verify_cmd')})")
        print(f"agent_cmd: {agent_template} (source: {get_source(args.agent, 'agent_cmd')})")
        models_str = ', '.join(models) if models else DEFAULT_MODELS
        models_source = get_source(args.models, 'models')
        print(f"models: {models_str} (source: {models_source})")
        print(f"test_model: {args.test_model} (source: {'CLI' if args.test_model else 'default'})")
        print(f"impl_model: {args.impl_model} (source: {'CLI' if args.impl_model else 'default'})")
        print(f"adversary_model: {args.adversary_model} (source: {'CLI' if args.adversary_model else 'default'})")
        print(f"max_cost: {args.max_cost} (source: {'CLI' if args.max_cost else 'default'})")
        print(f"max_tokens: {args.max_tokens} (source: {'CLI' if args.max_tokens else 'default'})")
        sys.exit(0)

    # Handle --self-check command
    if args.self_check:
        from src.verification.self_check import run_self_check
        success = run_self_check(
            verify_cmd=verify_cmd,
            diff_ref=args.self_check_ref,
            enable_adversarial_review=args.adversarial
        )
        sys.exit(0 if success else 1)

    # Handle --stats command
    if args.stats:
        from src.models.cost_tracker import AgentCostTracker
        tracker = AgentCostTracker()
        tracker.print_stats(days=args.stats_days)
        sys.exit(0)

    # Validate task argument
    if not args.task:
        parser.error("task argument is required (unless using --stats or --self-check)")

    loop = RalphLoop(
        agent_template, verify_cmd, MAX_RETRIES,
        models=models,
        test_model=args.test_model,
        impl_model=args.impl_model,
        adversary_model=args.adversary_model,
        max_cost_per_run=args.max_cost,
        max_tokens_per_run=args.max_tokens
    )
    success = loop.execute(args.task)

    # Strict enforcement: Exit with non-zero code on failure
    # This ensures precondition failures are detectable in CI/CD pipelines
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

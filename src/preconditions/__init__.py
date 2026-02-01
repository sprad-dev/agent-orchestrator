"""Execution preconditions module.

Safety checks before agent execution:
- Git clean working tree check
- Agent reachability check
- Tests exist check
- Timeout configuration
"""

from .checks import check_git_clean, check_tests_exist, check_agent_reachable

__all__ = [
    "check_git_clean",
    "check_tests_exist",
    "check_agent_reachable",
]

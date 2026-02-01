"""Shell execution and git utilities module."""

from .executor import run_shell, has_changes, get_diff_summary, get_diff_content

__all__ = [
    "run_shell",
    "has_changes",
    "get_diff_summary",
    "get_diff_content",
]

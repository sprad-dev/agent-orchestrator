"""Commit guards module.

Pre-commit safety checks:
- Secrets scanning in git diff
- Selective git add (only allowed file types)
- Commit message validation
- Human approval gate
"""

from .commit import CommitGuard

__all__ = [
    "CommitGuard",
]

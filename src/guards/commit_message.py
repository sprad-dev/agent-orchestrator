"""Commit message validation guard.

Validates commit message format: conventional commit prefix,
subject line length, body formatting.
"""

import re
from src.guards.commit import Guard, GuardResult
from src.shell import run_shell


# Conventional commit types
VALID_TYPES = {
    "feat", "fix", "docs", "style", "refactor",
    "perf", "test", "build", "ci", "chore", "revert",
}

# Pattern: type(optional-scope): description
CONVENTIONAL_PATTERN = re.compile(
    r"^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?!?:\s+(?P<description>.+)$"
)

MAX_SUBJECT_LENGTH = 72
MIN_SUBJECT_LENGTH = 10


class CommitMessageGuard(Guard):
    """Guard that validates commit message format."""

    def __init__(self, name: str = "commit_message", priority: int = 15,
                 require_conventional: bool = True,
                 max_subject_length: int = MAX_SUBJECT_LENGTH,
                 min_subject_length: int = MIN_SUBJECT_LENGTH):
        """Initialize commit message guard.

        Args:
            name: Guard identifier
            priority: Execution priority (lower runs first)
            require_conventional: Require conventional commit format
            max_subject_length: Maximum subject line length
            min_subject_length: Minimum subject line length
        """
        super().__init__(name, priority)
        self.require_conventional = require_conventional
        self.max_subject_length = max_subject_length
        self.min_subject_length = min_subject_length

    def check(self, message: str = None) -> GuardResult:
        """Validate commit message format.

        Args:
            message: Commit message to validate. If None, reads from
                     git's COMMIT_EDITMSG or last commit.

        Returns:
            GuardResult with validation outcome
        """
        if message is None:
            message = self._get_commit_message()

        if not message:
            return GuardResult(
                name=self.name, passed=False,
                issues=["Empty commit message"]
            )

        issues = []
        lines = message.strip().split("\n")
        subject = lines[0].strip()

        # Length checks
        if len(subject) > self.max_subject_length:
            issues.append(
                f"Subject line too long: {len(subject)} chars "
                f"(max {self.max_subject_length})"
            )

        if len(subject) < self.min_subject_length:
            issues.append(
                f"Subject line too short: {len(subject)} chars "
                f"(min {self.min_subject_length})"
            )

        # Conventional commit format
        if self.require_conventional:
            match = CONVENTIONAL_PATTERN.match(subject)
            if not match:
                issues.append(
                    f"Subject must follow conventional commit format: "
                    f"type(scope): description. Got: {subject!r}"
                )
            elif match.group("type") not in VALID_TYPES:
                issues.append(
                    f"Invalid commit type: {match.group('type')!r}. "
                    f"Valid types: {', '.join(sorted(VALID_TYPES))}"
                )

        # Body formatting: blank line after subject
        if len(lines) > 1 and lines[1].strip():
            issues.append(
                "Missing blank line between subject and body"
            )

        if issues:
            return GuardResult(name=self.name, passed=False, issues=issues)

        return GuardResult(name=self.name, passed=True, issues=[])

    def _get_commit_message(self) -> str:
        """Read commit message from git.

        Returns:
            Commit message string, or empty string on failure
        """
        # Try COMMIT_EDITMSG first (during commit hooks)
        success, output, _ = run_shell(
            "cat .git/COMMIT_EDITMSG 2>/dev/null", ignore_error=True
        )
        if success and output.strip():
            return output.strip()

        # Fall back to last commit message
        success, output, _ = run_shell(
            "git log -1 --format=%B", ignore_error=True
        )
        if success:
            return output.strip()

        return ""

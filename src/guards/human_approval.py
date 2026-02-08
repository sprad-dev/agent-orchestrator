"""Human approval gate for commit guards.

Prompts for human approval before allowing a commit,
with full audit logging of decisions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.guards.commit import Guard, GuardResult
from src.shell import run_shell, get_diff_content


class HumanApprovalGuard(Guard):
    """Guard that requires human approval before commit."""

    def __init__(self, name: str = "human_approval", priority: int = 90,
                 audit_log_path: Optional[str] = ".commit_audit.jsonl",
                 auto_approve: bool = False):
        """Initialize human approval guard.

        Args:
            name: Guard identifier
            priority: Execution priority (high = runs last)
            audit_log_path: Path to audit log (None disables)
            auto_approve: Auto-approve without prompting (for testing/CI)
        """
        super().__init__(name, priority)
        self.audit_log_path = Path(audit_log_path) if audit_log_path else None
        self.auto_approve = auto_approve

    def check(self) -> GuardResult:
        """Prompt for human approval of commit.

        Returns:
            GuardResult with approval decision
        """
        if self.auto_approve:
            self._log_decision(approved=True, reason="auto-approve")
            return GuardResult(name=self.name, passed=True, issues=[])

        # Get diff summary for display
        summary = self._get_diff_summary()

        print("\n" + "=" * 60)
        print("  COMMIT APPROVAL REQUIRED")
        print("=" * 60)

        if summary:
            print(f"\n{summary}")

        print("\nAll commit guards passed. Approve this commit? [y/N]: ",
              end="", flush=True)

        try:
            response = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            response = ""

        approved = response in ("y", "yes")
        reason = "approved" if approved else "rejected"

        self._log_decision(approved=approved, reason=reason, summary=summary)

        if approved:
            return GuardResult(name=self.name, passed=True, issues=[])

        return GuardResult(
            name=self.name, passed=False,
            issues=["Commit not approved by human reviewer"]
        )

    def _get_diff_summary(self) -> str:
        """Get a summary of staged changes.

        Returns:
            Diff stat summary string
        """
        success, output, _ = run_shell(
            "git diff --cached --stat 2>/dev/null || git diff --stat",
            ignore_error=True
        )
        return output.strip() if success else ""

    def _log_decision(self, approved: bool, reason: str,
                      summary: str = "") -> None:
        """Log approval decision to audit file.

        Args:
            approved: Whether commit was approved
            reason: Reason for decision
            summary: Diff summary that was reviewed
        """
        if not self.audit_log_path:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "approved": approved,
            "reason": reason,
            "diff_summary": summary,
        }

        try:
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except IOError:
            pass  # Don't fail commit because audit log is unwritable

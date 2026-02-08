"""L5: Human approval gate for verification pipeline.

Prompts for human approval before verification passes.
Logs approval decisions with timestamps for audit trail.
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.verification.layer import Layer, LayerResult, VerificationContext


class HumanApprovalLayer(Layer):
    """L5 layer that gates verification on human approval."""

    def __init__(self, audit_log_path: Optional[str] = None, auto_approve: bool = False):
        """Initialize human approval layer.

        Args:
            audit_log_path: Path to audit log file (None disables logging)
            auto_approve: If True, skip prompt and auto-approve (for testing/CI)
        """
        super().__init__()
        self.audit_log_path = Path(audit_log_path) if audit_log_path else None
        self.auto_approve = auto_approve

    @property
    def name(self) -> str:
        return "HumanApproval"

    @property
    def level(self) -> int:
        # Use level 50 to run after all other layers
        # Runner handles output formatting with "L5" label
        return 50

    def run(self, *, context: 'VerificationContext' = None, modified_files: Optional[List[str]] = None, **kwargs) -> LayerResult:
        """Prompt for human approval.

        Args:
            context: Optional VerificationContext (modified_files read from context)
            modified_files: List of files that were modified (overrides context)

        Returns:
            LayerResult with approval decision
        """
        if modified_files is None and context is not None:
            modified_files = context.modified_files
        if self.auto_approve:
            self._log_decision(approved=True, reason="auto-approve", files=modified_files)
            return LayerResult(passed=True, message="Human approval: auto-approved")

        # Display summary for review
        print("\n" + "=" * 60)
        print("  HUMAN APPROVAL REQUIRED")
        print("=" * 60)

        if modified_files:
            print(f"\nModified files ({len(modified_files)}):")
            for f in modified_files:
                print(f"  - {f}")

        print("\nAll verification layers (L1-L4) passed.")
        print("Approve these changes? [y/N]: ", end="", flush=True)

        try:
            response = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            response = ""

        approved = response in ("y", "yes")
        reason = "approved" if approved else "rejected"

        self._log_decision(approved=approved, reason=reason, files=modified_files)

        if approved:
            return LayerResult(passed=True, message="Human approval: approved")

        return LayerResult(
            passed=False,
            message="Human approval: rejected",
            error_details=["Changes were not approved by human reviewer"]
        )

    def _log_decision(self, approved: bool, reason: str,
                      files: Optional[List[str]] = None) -> None:
        """Log approval decision to audit file.

        Args:
            approved: Whether changes were approved
            reason: Reason for decision
            files: Files that were reviewed
        """
        if not self.audit_log_path:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "approved": approved,
            "reason": reason,
            "files": files or [],
        }

        # Append to audit log (JSONL format)
        try:
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except IOError:
            pass  # Don't fail verification because audit log is unwritable

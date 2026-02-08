"""Integration entrypoint verification layer.

This layer validates that code changes are properly integrated into the
existing system by checking:
1. Completion manifest has non-empty integration points
2. Delete test is specified (if new files were created)
3. Entrypoints mentioned in manifest actually exist (optional static check)

Based on Tier 0 backpressure mechanism: Integration Entrypoint Verification
from docs/tier0-backpressure-deep-dive.md
"""

import os
import re
from typing import Optional, List
from src.verification.layer import Layer, LayerResult, VerificationContext
from src.templates.completion_manifest import parse_completion_manifest
from src.shell import run_shell


class IntegrationCheckLayer(Layer):
    """Validates integration of new code into existing system.

    This layer enforces that:
    - New code has clear integration points
    - The "delete test" proves actual integration
    - Claimed entrypoints exist in the codebase
    """

    def __init__(self, strict_mode: bool = False):
        """Initialize integration check layer.

        Args:
            strict_mode: If True, validate entrypoints exist in code
        """
        super().__init__()
        self.strict_mode = strict_mode

    @property
    def name(self) -> str:
        """Layer name."""
        return "IntegrationCheck"

    @property
    def level(self) -> int:
        """Layer level (L4 - runs after tests pass)."""
        return 4

    def run(self, *, context: 'VerificationContext' = None, manifest_text: Optional[str] = None, **kwargs) -> LayerResult:
        """Execute integration verification.

        Args:
            context: Optional VerificationContext (manifest_text read from context)
            manifest_text: Completion manifest text from agent output (overrides context)
            **kwargs: Additional parameters (ignored)

        Returns:
            LayerResult with pass/fail status
        """
        if manifest_text is None and context is not None:
            manifest_text = context.manifest_text
        # If no manifest provided, try to extract from git log
        if not manifest_text:
            manifest_text = self._extract_manifest_from_commits()

        if not manifest_text:
            # No manifest found - check if there are new files
            new_files = self._get_new_files()
            if not new_files:
                # No new files created, integration check not applicable
                return LayerResult(
                    passed=True,
                    message="Integration check: No new files (modifications only)"
                )
            else:
                # New files but no manifest - fail
                return LayerResult(
                    passed=False,
                    message="Integration check: New files created but no completion manifest found",
                    error_details=[
                        "Expected COMPLETION MANIFEST in commit message or output",
                        f"New files: {', '.join(new_files[:5])}{'...' if len(new_files) > 5 else ''}"
                    ]
                )

        # Parse the manifest
        parsed = parse_completion_manifest(manifest_text)
        if parsed is None:
            return LayerResult(
                passed=False,
                message="Integration check: Completion manifest invalid or empty",
                error_details=[
                    "Manifest found but appears to be template-only (not filled out)",
                    "Expected filled sections: Integration Points, Delete Test"
                ]
            )

        # Check for integration points
        integration_errors = []

        # Extract integration points section
        integration_section = self._extract_section(manifest_text, "Integration Points")
        if not integration_section or "- None" in integration_section or "- No integration" in integration_section:
            # Check if files were actually modified (indicating integration)
            if parsed.get('files_modified_count', 0) == 0:
                integration_errors.append(
                    "No integration points documented and no existing files modified. "
                    "New code appears to be orphaned (not connected to existing system)."
                )

        # Check for delete test if new files were created
        if parsed.get('files_created_count', 0) > 0:
            delete_section = self._extract_section(manifest_text, "Delete Test")
            if not delete_section or "Not applicable" in delete_section:
                integration_errors.append(
                    f"Delete test missing. {parsed['files_created_count']} new file(s) created "
                    "but no delete test proving integration."
                )
            elif "Unknown" in delete_section or "[these tests/behaviors]" in delete_section:
                integration_errors.append(
                    "Delete test section filled with placeholder text. "
                    "Specify exact tests/behaviors that would break."
                )

        # Strict mode: Validate entrypoints exist
        if self.strict_mode and integration_section:
            entrypoint_errors = self._validate_entrypoints(integration_section)
            integration_errors.extend(entrypoint_errors)

        if integration_errors:
            return LayerResult(
                passed=False,
                message="Integration check: Integration verification failed",
                error_details=integration_errors
            )

        return LayerResult(
            passed=True,
            message="Integration check: Code properly integrated (manifest validated)"
        )

    def _extract_manifest_from_commits(self) -> Optional[str]:
        """Extract completion manifest from recent commit messages.

        Returns:
            Manifest text or None if not found
        """
        # Get last 3 commits
        success, output, _ = run_shell(
            "git log -3 --pretty=format:%B --no-color",
            ignore_error=True
        )

        if not success:
            return None

        # Look for COMPLETION MANIFEST in commit messages
        if "COMPLETION MANIFEST" in output:
            # Extract the manifest section
            start = output.find("COMPLETION MANIFEST")
            if start != -1:
                # Find the end (either next commit separator or end of output)
                end = output.find("━" * 70, start + 100)  # Look for closing line
                if end != -1:
                    end += 70  # Include closing line
                    return output[start:end]
                else:
                    return output[start:]

        return None

    def _get_new_files(self) -> List[str]:
        """Get list of new files in recent commits.

        Returns:
            List of new file paths
        """
        # Get files added in last commit
        success, output, _ = run_shell(
            "git diff --name-only --diff-filter=A HEAD~1..HEAD 2>/dev/null || "
            "git diff --name-only --diff-filter=A --cached",
            ignore_error=True
        )

        if not success or not output.strip():
            return []

        return [f.strip() for f in output.strip().split('\n') if f.strip()]

    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """Extract a specific section from manifest text.

        Args:
            text: Full manifest text
            section_name: Section header to extract

        Returns:
            Section content or None if not found
        """
        pattern = rf'## {re.escape(section_name)}\s*\n(.*?)(?=\n##|\n━|$)'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _validate_entrypoints(self, integration_section: str) -> List[str]:
        """Validate that entrypoints mentioned in manifest actually exist.

        Args:
            integration_section: Integration Points section text

        Returns:
            List of error messages (empty if all valid)
        """
        errors = []

        # Look for file paths with line numbers (e.g., "api/routes.py:42")
        entrypoint_pattern = r'([a-zA-Z0-9_/.-]+\.py):(\d+)'
        matches = re.findall(entrypoint_pattern, integration_section)

        for filepath, line_num in matches:
            # Check if file exists
            if not os.path.exists(filepath):
                errors.append(
                    f"Entrypoint file not found: {filepath}:{line_num} "
                    "(mentioned in integration points)"
                )
                continue

            # Optional: Check if line number is valid
            try:
                with open(filepath, 'r') as f:
                    lines = f.readlines()
                    if int(line_num) > len(lines):
                        errors.append(
                            f"Invalid line number: {filepath}:{line_num} "
                            f"(file only has {len(lines)} lines)"
                        )
            except Exception as e:
                errors.append(
                    f"Could not validate {filepath}:{line_num}: {str(e)}"
                )

        return errors

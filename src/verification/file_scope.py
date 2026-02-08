"""L2: File scope validation.

Verify agents only modify authorized files within expected scope.
Blocks changes to critical system files, config, or out-of-scope areas.
"""

from pathlib import Path
from typing import List, Optional, Set
import fnmatch
from src.verification.layer import Layer, LayerResult, VerificationContext
from src.shell import run_shell


class FileScopeLayer(Layer):
    """L2: File scope validation layer."""

    def __init__(self, allowed_patterns: Optional[List[str]] = None):
        """Initialize file scope layer.

        Args:
            allowed_patterns: List of glob patterns for allowed files.
                             If None, all files are allowed (no restrictions).
                             Examples: ["src/**/*.py", "tests/**/*.py"]
        """
        super().__init__()
        self.allowed_patterns = allowed_patterns

    @property
    def name(self) -> str:
        """Layer name."""
        return "FileScope"

    @property
    def level(self) -> int:
        """Layer level (L2)."""
        return 2

    def run(self, *, context: 'VerificationContext' = None, **kwargs) -> LayerResult:
        """Verify changed files are within allowed scope.

        Args:
            context: Optional VerificationContext with shared pipeline state
            **kwargs: Ignored (for compatibility)

        Returns:
            LayerResult with validation status
        """
        # If no restrictions, allow everything
        if self.allowed_patterns is None:
            return LayerResult(
                passed=True,
                message="File scope unrestricted (no allowed_patterns set)"
            )

        # Get changed files from git
        changed_files = self._get_changed_files()

        if not changed_files:
            return LayerResult(
                passed=True,
                message="No files changed"
            )

        # Check each file against allowed patterns
        unauthorized_files = []
        for file_path in changed_files:
            if not self._is_file_allowed(file_path):
                unauthorized_files.append(file_path)

        if unauthorized_files:
            error_msg = "Files modified outside allowed scope (BLOCKED)"
            return LayerResult(
                passed=False,
                message=error_msg,
                error_details=[
                    f"Unauthorized: {f}" for f in unauthorized_files
                ] + [
                    f"Allowed patterns: {', '.join(self.allowed_patterns)}"
                ]
            )

        return LayerResult(
            passed=True,
            message=f"File scope valid: {len(changed_files)} file(s) in allowed scope"
        )

    def _get_changed_files(self) -> Set[str]:
        """Get list of changed files from git.

        Returns:
            Set of file paths that have been modified
        """
        # Get files in working tree (unstaged and staged)
        success, output, _ = run_shell(
            "git diff --name-only HEAD",
            ignore_error=True
        )

        if not success:
            return set()

        files = set()
        for line in output.strip().split('\n'):
            line = line.strip()
            if line:
                files.add(line)

        return files

    def _is_file_allowed(self, file_path: str) -> bool:
        """Check if file matches any allowed pattern.

        Args:
            file_path: Path to check

        Returns:
            True if file matches at least one allowed pattern
        """
        if self.allowed_patterns is None:
            return True

        for pattern in self.allowed_patterns:
            # Handle ** recursive glob patterns manually
            if '**' in pattern:
                # Convert glob pattern to match from the root
                # src/**/*.py should match src/main.py and src/foo/bar.py
                if self._glob_match_recursive(file_path, pattern):
                    return True
            # Use fnmatch for simple patterns
            elif fnmatch.fnmatch(file_path, pattern):
                return True

        return False

    def _glob_match_recursive(self, file_path: str, pattern: str) -> bool:
        """Match file path against glob pattern with ** support.

        Args:
            file_path: File path to match
            pattern: Glob pattern (may contain **)

        Returns:
            True if file matches pattern
        """
        # Split pattern on /**/ to get parts
        parts = pattern.split('**/')

        if len(parts) == 1:
            # No ** in pattern, use regular fnmatch
            return fnmatch.fnmatch(file_path, pattern)

        # Check if file starts with the prefix before **
        prefix = parts[0]
        if prefix and not file_path.startswith(prefix):
            return False

        # Check if file ends with the suffix after **
        suffix = parts[-1] if len(parts) > 1 else ""
        if suffix:
            # Extract the part after the prefix
            remainder = file_path[len(prefix):] if prefix else file_path
            # Match suffix pattern against remainder or any sub-path
            return fnmatch.fnmatch(remainder, suffix) or fnmatch.fnmatch(Path(remainder).name, suffix)

        return True

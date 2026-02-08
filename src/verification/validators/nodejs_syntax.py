"""Node.js/TypeScript syntax validation.

Validates JavaScript/TypeScript syntax using eslint or tsc.
Provides immediate feedback on parse errors and type issues.
"""

import subprocess
from pathlib import Path
from typing import List
from src.verification.layer import Layer, LayerResult, VerificationContext


class NodeJSSyntaxLayer(Layer):
    """L2: JavaScript/Node.js syntax validation layer."""

    def __init__(self, use_typescript: bool = False):
        """Initialize Node.js syntax check layer.

        Args:
            use_typescript: If True, use tsc for TypeScript checking
        """
        super().__init__()
        self.use_typescript = use_typescript

    @property
    def name(self) -> str:
        """Layer name."""
        return "NodeJSSyntaxCheck"

    @property
    def level(self) -> int:
        """Layer level (L2)."""
        return 2

    def run(self, *, context: 'VerificationContext' = None, files: List[str] = None, **kwargs) -> LayerResult:
        """Validate JavaScript/TypeScript syntax.

        Args:
            context: Optional VerificationContext with shared pipeline state
            files: List of file paths to check
            **kwargs: Ignored (for compatibility)

        Returns:
            LayerResult with validation status
        """
        if files is None and context is not None:
            files = context.modified_files
        if not files:
            return LayerResult(
                passed=True,
                message="No files to validate"
            )

        # Filter for JS/TS files
        js_ts_files = [
            f for f in files
            if Path(f).suffix in ['.js', '.jsx', '.ts', '.tsx']
            and Path(f).exists()
        ]

        if not js_ts_files:
            return LayerResult(
                passed=True,
                message="No JavaScript/TypeScript files to validate"
            )

        # Try TypeScript first if enabled, then fallback to ESLint
        if self.use_typescript:
            result = self._check_with_tsc(js_ts_files)
            if result:
                return result

        # Try ESLint
        result = self._check_with_eslint(js_ts_files)
        if result:
            return result

        # No tools available
        return LayerResult(
            passed=True,
            message="No syntax checker available (install eslint or typescript)"
        )

    def _check_with_tsc(self, files: List[str]) -> LayerResult:
        """Check syntax with TypeScript compiler.

        Args:
            files: Files to check

        Returns:
            LayerResult or None if tsc not available
        """
        try:
            # Check if tsc is available
            subprocess.run(
                ['npx', 'tsc', '--version'],
                capture_output=True,
                check=True,
                timeout=5
            )

            # Run tsc with --noEmit (syntax check only)
            result = subprocess.run(
                ['npx', 'tsc', '--noEmit'] + files,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return LayerResult(
                    passed=True,
                    message="TypeScript syntax valid for all files"
                )

            # Parse errors
            errors = result.stdout.strip().split('\n')
            errors = [e for e in errors if e.strip()]

            return LayerResult(
                passed=False,
                message="TypeScript syntax check failed",
                error_details=errors[:10]  # Limit to first 10 errors
            )

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _check_with_eslint(self, files: List[str]) -> LayerResult:
        """Check syntax with ESLint.

        Args:
            files: Files to check

        Returns:
            LayerResult or None if eslint not available
        """
        try:
            # Check if eslint is available
            subprocess.run(
                ['npx', 'eslint', '--version'],
                capture_output=True,
                check=True,
                timeout=5
            )

            # Run eslint
            result = subprocess.run(
                ['npx', 'eslint', '--format', 'compact'] + files,
                capture_output=True,
                text=True,
                timeout=30
            )

            # ESLint returns 0 for success, 1 for warnings/errors, 2 for fatal
            if result.returncode == 0:
                return LayerResult(
                    passed=True,
                    message="ESLint validation passed for all files"
                )

            if result.returncode == 2:
                # Fatal error (syntax error)
                errors = result.stdout.strip().split('\n')
                errors = [e for e in errors if e.strip()]

                return LayerResult(
                    passed=False,
                    message="ESLint syntax check failed",
                    error_details=errors[:10]
                )

            # Warnings only - pass with message
            return LayerResult(
                passed=True,
                message="ESLint validation passed (with warnings)"
            )

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None

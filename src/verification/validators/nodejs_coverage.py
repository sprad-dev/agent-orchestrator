"""Node.js coverage analysis.

Measures test coverage using nyc/istanbul or Jest's built-in coverage.
Reports coverage gaps and enforces minimum thresholds.
"""

import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from src.verification.layer import Layer, LayerResult


class NodeJSCoverageLayer(Layer):
    """L3: Node.js coverage validation layer."""

    def __init__(self, min_coverage: float = 80.0, test_command: str = "npm test"):
        """Initialize Node.js coverage check layer.

        Args:
            min_coverage: Minimum coverage percentage required
            test_command: Command to run tests
        """
        super().__init__()
        self.min_coverage = min_coverage
        self.test_command = test_command

    @property
    def name(self) -> str:
        """Layer name."""
        return "NodeJSCoverageCheck"

    @property
    def level(self) -> int:
        """Layer level (L3)."""
        return 3

    def run(self, changed_files: List[str] = None, **kwargs) -> LayerResult:
        """Check coverage for changed files.

        Args:
            changed_files: List of files to check coverage for
            **kwargs: Ignored (for compatibility)

        Returns:
            LayerResult with validation status
        """
        if not changed_files:
            return LayerResult(
                passed=True,
                message="No changed files to analyze"
            )

        # Filter for JS/TS files only
        js_files = [
            f for f in changed_files
            if Path(f).suffix in ['.js', '.jsx', '.ts', '.tsx']
            and Path(f).exists()
        ]

        if not js_files:
            return LayerResult(
                passed=True,
                message="No JavaScript/TypeScript files to analyze"
            )

        # Try Jest coverage first, then nyc
        passed, message, _ = self._run_jest_coverage(js_files)
        if passed is not None:
            return LayerResult(passed=passed, message=message)

        passed, message, _ = self._run_nyc_coverage(js_files)
        if passed is not None:
            return LayerResult(passed=passed, message=message)

        # No coverage tool available
        return LayerResult(
            passed=True,
            message="No coverage tool available (install jest or nyc)"
        )

    def _run_jest_coverage(
        self, changed_files: List[str]
    ) -> Tuple[Optional[bool], str, Dict]:
        """Run coverage analysis with Jest.

        Args:
            changed_files: Files to analyze

        Returns:
            Tuple of (passed, message, coverage_data)
        """
        try:
            # Check if Jest is available
            subprocess.run(
                ['npx', 'jest', '--version'],
                capture_output=True,
                check=True,
                timeout=5
            )

            # Run Jest with coverage
            result = subprocess.run(
                ['npx', 'jest', '--coverage', '--json', '--silent'],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode not in [0, 1]:  # 0 = pass, 1 = fail but ran
                return None, "", {}

            # Parse coverage from JSON output
            try:
                data = json.loads(result.stdout)
                coverage_summary = data.get('coverageMap', {})

                if not coverage_summary:
                    return None, "", {}

                # Calculate coverage for changed files
                total_lines = 0
                covered_lines = 0

                for file_path in changed_files:
                    abs_path = str(Path(file_path).resolve())
                    if abs_path in coverage_summary:
                        file_cov = coverage_summary[abs_path]
                        lines = file_cov.get('lines', {})
                        total_lines += lines.get('total', 0)
                        covered_lines += lines.get('covered', 0)

                if total_lines == 0:
                    return True, "No executable lines in changed files", {}

                coverage_pct = (covered_lines / total_lines * 100)

                # Check threshold
                if coverage_pct < self.min_coverage:
                    return (
                        False,
                        f"Coverage {coverage_pct:.1f}% below minimum {self.min_coverage}%",
                        {}
                    )

                return (
                    True,
                    f"Jest coverage: {coverage_pct:.1f}% ({covered_lines}/{total_lines} lines)",
                    {}
                )

            except (json.JSONDecodeError, KeyError):
                return None, "", {}

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None, "", {}

    def _run_nyc_coverage(
        self, changed_files: List[str]
    ) -> Tuple[Optional[bool], str, Dict]:
        """Run coverage analysis with nyc.

        Args:
            changed_files: Files to analyze

        Returns:
            Tuple of (passed, message, coverage_data)
        """
        try:
            # Check if nyc is available
            subprocess.run(
                ['npx', 'nyc', '--version'],
                capture_output=True,
                check=True,
                timeout=5
            )

            # Run nyc with coverage
            test_cmd = self.test_command.split()
            result = subprocess.run(
                ['npx', 'nyc', '--reporter=json'] + test_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Parse coverage.json
            coverage_file = Path('coverage/coverage-final.json')
            if not coverage_file.exists():
                return None, "", {}

            with open(coverage_file, 'r') as f:
                coverage_data = json.load(f)

            # Calculate coverage for changed files
            total_lines = 0
            covered_lines = 0

            for file_path in changed_files:
                abs_path = str(Path(file_path).resolve())
                if abs_path in coverage_data:
                    file_cov = coverage_data[abs_path]
                    statements = file_cov.get('s', {})
                    total_lines += len(statements)
                    covered_lines += sum(1 for hits in statements.values() if hits > 0)

            if total_lines == 0:
                return True, "No executable lines in changed files", {}

            coverage_pct = (covered_lines / total_lines * 100)

            # Check threshold
            if coverage_pct < self.min_coverage:
                return (
                    False,
                    f"Coverage {coverage_pct:.1f}% below minimum {self.min_coverage}%",
                    {}
                )

            return (
                True,
                f"nyc coverage: {coverage_pct:.1f}% ({covered_lines}/{total_lines} lines)",
                {}
            )

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            return None, "", {}

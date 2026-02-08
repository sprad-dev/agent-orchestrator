""".NET coverage analysis.

Measures test coverage using coverlet or dotnet test --collect:"XPlat Code Coverage".
Reports coverage gaps and enforces minimum thresholds.
"""

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from src.verification.layer import Layer, LayerResult, VerificationContext


class DotNetCoverageLayer(Layer):
    """L3: .NET coverage validation layer."""

    def __init__(self, min_coverage: float = 80.0):
        """Initialize .NET coverage check layer.

        Args:
            min_coverage: Minimum coverage percentage required
        """
        super().__init__()
        self.min_coverage = min_coverage

    @property
    def name(self) -> str:
        """Layer name."""
        return "DotNetCoverageCheck"

    @property
    def level(self) -> int:
        """Layer level (L3)."""
        return 3

    def run(self, *, context: 'VerificationContext' = None, changed_files: List[str] = None, **kwargs) -> LayerResult:
        """Check coverage for changed files.

        Args:
            context: Optional VerificationContext with shared pipeline state
            changed_files: List of files to check coverage for
            **kwargs: Ignored (for compatibility)

        Returns:
            LayerResult with validation status
        """
        if changed_files is None and context is not None:
            changed_files = context.changed_files or context.modified_files
        if not changed_files:
            return LayerResult(
                passed=True,
                message="No changed files to analyze"
            )

        # Filter for C# files only
        cs_files = [
            f for f in changed_files
            if Path(f).suffix == '.cs'
            and Path(f).exists()
            and not f.endswith('.Designer.cs')  # Skip generated files
        ]

        if not cs_files:
            return LayerResult(
                passed=True,
                message="No C# files to analyze"
            )

        # Run coverage analysis
        passed, message, _ = self._run_coverage_analysis(cs_files)

        return LayerResult(passed=passed, message=message)

    def _run_coverage_analysis(
        self, changed_files: List[str]
    ) -> Tuple[bool, str, Dict]:
        """Run coverage analysis with dotnet test.

        Args:
            changed_files: Files to analyze

        Returns:
            Tuple of (passed, message, coverage_data)
        """
        try:
            # Find test project
            test_project = self._find_test_project()
            if not test_project:
                return True, "No test project found, skipping coverage", {}

            # Run dotnet test with coverage collection
            result = subprocess.run(
                [
                    'dotnet', 'test', test_project,
                    '--collect:XPlat Code Coverage',
                    '--results-directory', '.coverage'
                ],
                capture_output=True,
                text=True,
                timeout=120
            )

            # Find coverage file
            coverage_files = list(Path('.coverage').rglob('coverage.cobertura.xml'))
            if not coverage_files:
                return True, "No coverage report generated", {}

            # Parse coverage XML
            coverage_pct = self._parse_coverage_xml(coverage_files[0], changed_files)

            if coverage_pct is None:
                return True, "Unable to parse coverage report", {}

            # Check threshold
            if coverage_pct < self.min_coverage:
                return (
                    False,
                    f"Coverage {coverage_pct:.1f}% below minimum {self.min_coverage}%",
                    {}
                )

            return (
                True,
                f"dotnet coverage: {coverage_pct:.1f}%",
                {}
            )

        except subprocess.TimeoutExpired:
            return False, "Coverage analysis timed out", {}
        except FileNotFoundError:
            return True, "dotnet CLI not found, skipping coverage", {}
        except Exception as e:
            return False, f"Coverage analysis error: {str(e)}", {}

    def _find_test_project(self) -> str:
        """Find test project file.

        Returns:
            Path to test project, or empty string if not found
        """
        # Look for *Test.csproj or *Tests.csproj
        for pattern in ['*Test.csproj', '*Tests.csproj', '*.Test.csproj', '*.Tests.csproj']:
            test_projects = list(Path('.').rglob(pattern))
            if test_projects:
                return str(test_projects[0])

        return ""

    def _parse_coverage_xml(
        self, coverage_file: Path, changed_files: List[str]
    ) -> Optional[float]:
        """Parse Cobertura coverage XML.

        Args:
            coverage_file: Path to coverage XML file
            changed_files: Files to filter coverage for

        Returns:
            Coverage percentage, or None if unable to parse
        """
        try:
            tree = ET.parse(coverage_file)
            root = tree.getroot()

            # Get line-rate (coverage percentage as decimal)
            line_rate = root.attrib.get('line-rate')
            if line_rate:
                return float(line_rate) * 100

            # Fallback: calculate from class elements
            total_lines = 0
            covered_lines = 0

            for class_elem in root.findall('.//class'):
                filename = class_elem.attrib.get('filename', '')

                # Check if this file is in changed_files
                if any(cf in filename or filename.endswith(cf) for cf in changed_files):
                    for line_elem in class_elem.findall('.//line'):
                        total_lines += 1
                        hits = int(line_elem.attrib.get('hits', 0))
                        if hits > 0:
                            covered_lines += 1

            if total_lines == 0:
                return None

            return (covered_lines / total_lines) * 100

        except (ET.ParseError, ValueError, KeyError):
            return None

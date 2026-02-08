"""L3: Coverage analysis for changed files.

Measures test coverage specifically on changed files using coverage.py.
Reports coverage gaps and optionally enforces minimum coverage thresholds.
"""

import subprocess
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from src.verification.layer import Layer, LayerResult, VerificationContext


def get_changed_files(base_ref: str = "HEAD") -> List[str]:
    """Get list of changed Python files from git.
    
    Args:
        base_ref: Git reference to compare against (default: HEAD for uncommitted changes)
        
    Returns:
        List of changed Python file paths
    """
    try:
        # Get uncommitted changes
        result = subprocess.run(
            ['git', 'diff', '--name-only', base_ref],
            capture_output=True,
            text=True,
            check=True
        )
        files = result.stdout.strip().split('\n')
        
        # Filter for Python files only
        python_files = [f for f in files if f.endswith('.py') and Path(f).exists()]
        
        return python_files
    except subprocess.CalledProcessError:
        return []
    except Exception:
        return []


class CoverageCheckLayer(Layer):
    """L3: Coverage validation layer."""
    
    def __init__(self, min_coverage: float = 80.0, test_command: str = "pytest"):
        """Initialize coverage check layer.
        
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
        return "CoverageCheck"
    
    @property
    def level(self) -> int:
        """Layer level (L3)."""
        return 3
    
    def run(self, *, context: 'VerificationContext' = None, changed_files: List[str] = None, **kwargs) -> LayerResult:
        """Check coverage for changed files.

        Args:
            context: Optional VerificationContext (changed_files read from context)
            changed_files: List of files to check coverage for (overrides context)
            **kwargs: Ignored (for compatibility)

        Returns:
            LayerResult with validation status
        """
        if changed_files is None and context is not None:
            changed_files = context.changed_files
        passed, message, _ = run_coverage_analysis(
            self.test_command,
            changed_files,
            self.min_coverage
        )
        
        return LayerResult(
            passed=passed,
            message=message
        )


def _run_coverage_command(test_command: str, timeout: int = 60) -> Tuple[bool, str]:
    """Run coverage collection command.
    
    Args:
        test_command: Test command to run with coverage
        timeout: Maximum seconds to wait
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        cmd = [
            'coverage', 'run', '--source=.',
            '-m', test_command.replace('pytest', '').strip() or 'pytest'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "Coverage analysis timed out"
    except Exception as e:
        return False, f"Coverage analysis error: {str(e)}"


def _generate_coverage_json(output_path: str = "/tmp/coverage.json") -> Tuple[bool, str]:
    """Generate coverage report in JSON format.
    
    Args:
        output_path: Path to write JSON report
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        result = subprocess.run(
            ['coverage', 'json', '-o', output_path],
            capture_output=True,
            text=True
        )
        return result.returncode == 0, ""
    except Exception as e:
        return False, f"Failed to generate coverage JSON: {str(e)}"


def _parse_coverage_for_files(
    json_path: str,
    target_files: List[str]
) -> Dict[str, Dict]:
    """Extract coverage data for specific files from JSON report.
    
    Args:
        json_path: Path to coverage JSON file
        target_files: List of files to extract coverage for
        
    Returns:
        Dict mapping file paths to coverage data
    """
    coverage_data = {}
    
    try:
        with open(json_path, 'r') as f:
            full_coverage = json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}
    
    for file_path in target_files:
        abs_path = str(Path(file_path).resolve())
        if abs_path in full_coverage.get('files', {}):
            file_cov = full_coverage['files'][abs_path]
            coverage_data[file_path] = {
                'percent_covered': file_cov['summary']['percent_covered'],
                'missing_lines': file_cov['missing_lines'],
                'covered_lines': file_cov['summary']['covered_lines'],
                'total_lines': file_cov['summary']['num_statements']
            }
        elif Path(file_path).exists():
            # File exists but not in coverage report (not executed)
            coverage_data[file_path] = {
                'percent_covered': 0.0,
                'missing_lines': [],
                'covered_lines': 0,
                'total_lines': 0
            }
    
    return coverage_data


def _calculate_average_coverage(coverage_data: Dict[str, Dict]) -> float:
    """Calculate average coverage across files.
    
    Args:
        coverage_data: Dict mapping file paths to coverage data
        
    Returns:
        Average coverage percentage
    """
    if not coverage_data:
        return 0.0
    
    total_covered = sum(d['covered_lines'] for d in coverage_data.values())
    total_lines = sum(d['total_lines'] for d in coverage_data.values())
    
    return (total_covered / total_lines * 100) if total_lines > 0 else 0.0


def _format_coverage_message(
    file_count: int,
    coverage_data: Dict[str, Dict],
    avg_coverage: float,
    min_coverage: Optional[float] = None
) -> Tuple[bool, str]:
    """Build coverage report message.
    
    Args:
        file_count: Number of files analyzed
        coverage_data: Coverage data per file
        avg_coverage: Average coverage percentage
        min_coverage: Optional minimum threshold
        
    Returns:
        Tuple of (passed, message)
    """
    message_parts = [f"Coverage analysis: {file_count} file(s) analyzed"]
    
    if coverage_data:
        message_parts.append(f"Average coverage: {avg_coverage:.1f}%")
        for file_path, data in coverage_data.items():
            message_parts.append(
                f"  {file_path}: {data['percent_covered']:.1f}% "
                f"({data['covered_lines']}/{data['total_lines']} lines)"
            )
    
    passed = True
    if min_coverage is not None and coverage_data:
        if avg_coverage < min_coverage:
            passed = False
            message_parts.append(
                f"FAILED: Coverage {avg_coverage:.1f}% below minimum {min_coverage}%"
            )
    
    return passed, "\n".join(message_parts)


def run_coverage_analysis(
    test_command: str = "pytest",
    changed_files: Optional[List[str]] = None,
    min_coverage: Optional[float] = None
) -> Tuple[bool, str, Dict]:
    """Run coverage analysis on changed files.
    
    Args:
        test_command: Command to run tests (default: "pytest")
        changed_files: List of files to check coverage for (if None, auto-detect from git)
        min_coverage: Minimum coverage percentage required (optional)
        
    Returns:
        Tuple of (passed, message, coverage_data)
        - passed: True if coverage meets requirements
        - message: Human-readable status message
        - coverage_data: Dict with coverage details per file
    """
    # Get changed files if not provided
    if changed_files is None:
        changed_files = get_changed_files()
    
    # Skip if no changed files
    if not changed_files:
        return True, "No changed Python files to analyze", {}
    
    # Filter for existing files only
    existing_files = [f for f in changed_files if Path(f).exists()]
    if not existing_files:
        return True, "No existing Python files to analyze", {}
    
    # Run coverage command
    success, error_msg = _run_coverage_command(test_command)
    if not success:
        return False, error_msg, {}
    
    # Generate JSON report
    json_path = '/tmp/coverage.json'
    success, error_msg = _generate_coverage_json(json_path)
    if not success:
        return False, "Failed to read coverage report", {}
    
    # Parse coverage for target files
    coverage_data = _parse_coverage_for_files(json_path, existing_files)
    
    # Calculate average coverage
    avg_coverage = _calculate_average_coverage(coverage_data)
    
    # Format message and check threshold
    passed, message = _format_coverage_message(
        len(existing_files),
        coverage_data,
        avg_coverage,
        min_coverage
    )
    
    return passed, message, coverage_data


def check_coverage(
    changed_files: Optional[List[str]] = None,
    min_coverage: float = 80.0,
    test_command: str = "pytest"
) -> Tuple[bool, str]:
    """Check coverage for changed files with minimum threshold.
    
    Deprecated: Use CoverageCheckLayer.run() instead.
    Kept for backwards compatibility.
    
    Args:
        changed_files: List of files to check (if None, auto-detect from git)
        min_coverage: Minimum coverage percentage required (default: 80%)
        test_command: Command to run tests (default: "pytest")
        
    Returns:
        Tuple of (passed, message)
    """
    passed, message, _ = run_coverage_analysis(test_command, changed_files, min_coverage)
    return passed, message


def get_coverage_report(
    changed_files: Optional[List[str]] = None,
    test_command: str = "pytest"
) -> Dict:
    """Get coverage data for changed files without enforcing thresholds.
    
    Args:
        changed_files: List of files to check (if None, auto-detect from git)
        test_command: Command to run tests (default: "pytest")
        
    Returns:
        Dict with coverage data per file
    """
    _, _, coverage_data = run_coverage_analysis(test_command, changed_files, None)
    return coverage_data

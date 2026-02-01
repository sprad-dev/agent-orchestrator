"""L3: Coverage analysis for changed files.

Measures test coverage specifically on changed files using coverage.py.
Reports coverage gaps and optionally enforces minimum coverage thresholds.
"""

import subprocess
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional


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
    
    # Run coverage on the changed files
    coverage_data = {}
    try:
        # Run pytest with coverage
        cmd = [
            'coverage', 'run', '--source=.',
            '-m', test_command.replace('pytest', '').strip() or 'pytest'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Generate coverage report in JSON format
        json_result = subprocess.run(
            ['coverage', 'json', '-o', '/tmp/coverage.json'],
            capture_output=True,
            text=True
        )
        
        # Parse coverage data
        if json_result.returncode == 0:
            try:
                with open('/tmp/coverage.json', 'r') as f:
                    full_coverage = json.load(f)
            except (IOError, json.JSONDecodeError):
                return False, "Failed to read coverage report", {}
            
            # Extract coverage for changed files only
            for file_path in existing_files:
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
                    # File exists but not in coverage report (likely not executed)
                    coverage_data[file_path] = {
                        'percent_covered': 0.0,
                        'missing_lines': [],
                        'covered_lines': 0,
                        'total_lines': 0
                    }
        
        # Calculate average coverage
        if coverage_data:
            total_covered = sum(d['covered_lines'] for d in coverage_data.values())
            total_lines = sum(d['total_lines'] for d in coverage_data.values())
            avg_coverage = (total_covered / total_lines * 100) if total_lines > 0 else 0.0
        else:
            avg_coverage = 0.0
        
        # Build report message
        message_parts = [f"Coverage analysis: {len(existing_files)} file(s) analyzed"]
        
        if coverage_data:
            message_parts.append(f"Average coverage: {avg_coverage:.1f}%")
            for file_path, data in coverage_data.items():
                message_parts.append(
                    f"  {file_path}: {data['percent_covered']:.1f}% "
                    f"({data['covered_lines']}/{data['total_lines']} lines)"
                )
        
        # Check minimum coverage threshold
        passed = True
        if min_coverage is not None and coverage_data:
            if avg_coverage < min_coverage:
                passed = False
                message_parts.append(
                    f"FAILED: Coverage {avg_coverage:.1f}% below minimum {min_coverage}%"
                )
        
        message = "\n".join(message_parts)
        return passed, message, coverage_data
        
    except subprocess.TimeoutExpired:
        return False, "Coverage analysis timed out", {}
    except Exception as e:
        return False, f"Coverage analysis error: {str(e)}", {}


def check_coverage(
    changed_files: Optional[List[str]] = None,
    min_coverage: float = 80.0,
    test_command: str = "pytest"
) -> Tuple[bool, str]:
    """Check coverage for changed files with minimum threshold.
    
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

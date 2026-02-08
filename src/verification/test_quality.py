"""L6: Static test quality analysis layer.

AST-based analysis that flags low-quality test patterns:
- Mock-only tests (all assertions are mock-related, no value checks)
- No-assertion tests (test functions with zero assert statements)
- Trivial assertions (only assertTrue(True), assertIsNotNone(result))

Advisory layer — warns but does not block the pipeline.
"""

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.verification.layer import Layer, LayerResult


@dataclass
class TestIssue:
    """A quality issue found in a test."""
    __test__ = False  # Prevent pytest from collecting this class
    file: str
    function: str
    issue_type: str  # "mock_only", "no_assertion", "trivial_assertion"
    detail: str


MOCK_ASSERT_NAMES = {
    "assert_called",
    "assert_called_once",
    "assert_called_with",
    "assert_called_once_with",
    "assert_any_call",
    "assert_has_calls",
    "assert_not_called",
}

TRIVIAL_PATTERNS = {
    # assertTrue(True)
    ("assertTrue", True),
    # assertIsNotNone with just a name (result variable)
    ("assertIsNotNone", None),
}


def _is_mock_assertion(node: ast.AST) -> bool:
    """Check if a node is a mock assertion call (e.g., mock.assert_called_once_with(...))."""
    if not isinstance(node, ast.Expr):
        return False
    call = node.value
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in MOCK_ASSERT_NAMES:
        return True
    return False


def _is_assert_statement(node: ast.AST) -> bool:
    """Check if a node is an assert statement or unittest assert call."""
    # Plain assert statement
    if isinstance(node, ast.Assert):
        return True
    # self.assert* calls or pytest assert
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        func = node.value.func
        if isinstance(func, ast.Attribute) and func.attr.startswith("assert"):
            return True
    return False


def _is_trivial_assertion(node: ast.AST) -> bool:
    """Check if an assertion is trivially true (e.g., assertTrue(True))."""
    if isinstance(node, ast.Assert):
        # assert True
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            return True
        return False

    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False

    call = node.value
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False

    # assertTrue(True)
    if func.attr == "assertTrue" and len(call.args) >= 1:
        arg = call.args[0]
        if isinstance(arg, ast.Constant) and arg.value is True:
            return True

    # assertIsNotNone(result) where result is just a name — trivial
    if func.attr == "assertIsNotNone" and len(call.args) == 1:
        if isinstance(call.args[0], ast.Name):
            return True

    return False


def analyze_test_file(filepath: str) -> List[TestIssue]:
    """Analyze a single test file for quality issues.

    Args:
        filepath: Path to the test file

    Returns:
        List of TestIssue found
    """
    issues = []
    try:
        with open(filepath, "r") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, OSError):
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue

        assertions = []
        mock_assertions = []
        trivial_assertions = []

        for child in ast.walk(node):
            if _is_mock_assertion(child):
                mock_assertions.append(child)
            elif _is_assert_statement(child):
                assertions.append(child)
                if _is_trivial_assertion(child):
                    trivial_assertions.append(child)

        total_asserts = len(assertions) + len(mock_assertions)

        # No assertions at all
        if total_asserts == 0:
            issues.append(TestIssue(
                file=filepath,
                function=node.name,
                issue_type="no_assertion",
                detail="Test function has no assertions"
            ))
            continue

        # Mock-only: has mock assertions but zero value assertions
        if mock_assertions and len(assertions) == 0:
            issues.append(TestIssue(
                file=filepath,
                function=node.name,
                issue_type="mock_only",
                detail=f"All {len(mock_assertions)} assertion(s) are mock-related, no value checks"
            ))
            continue

        # All value assertions are trivial
        if assertions and len(trivial_assertions) == len(assertions) and len(mock_assertions) == 0:
            issues.append(TestIssue(
                file=filepath,
                function=node.name,
                issue_type="trivial_assertion",
                detail=f"All {len(assertions)} assertion(s) are trivially true"
            ))

    return issues


def find_test_files(project_path: str = ".") -> List[str]:
    """Find all test files in a project.

    Args:
        project_path: Root directory to search

    Returns:
        List of test file paths
    """
    test_files = []
    for root, dirs, files in os.walk(project_path):
        # Skip common non-test directories
        dirs[:] = [d for d in dirs if d not in {
            "__pycache__", ".git", ".venv", "venv", "node_modules",
            ".tox", ".mypy_cache", ".pytest_cache", "dist", "build"
        }]
        for fname in files:
            if (fname.startswith("test_") or fname.endswith("_test.py")) and fname.endswith(".py"):
                test_files.append(os.path.join(root, fname))
    return test_files


def analyze_test_quality(
    project_path: str = ".",
    test_files: Optional[List[str]] = None
) -> List[TestIssue]:
    """Analyze test quality across a project.

    Args:
        project_path: Root directory to search for test files
        test_files: Optional explicit list of test files (overrides search)

    Returns:
        List of all TestIssue found
    """
    if test_files is None:
        test_files = find_test_files(project_path)

    all_issues = []
    for filepath in test_files:
        if filepath.endswith(".py") and (
            os.path.basename(filepath).startswith("test_") or
            filepath.endswith("_test.py")
        ):
            all_issues.extend(analyze_test_file(filepath))
    return all_issues


class TestQualityLayer(Layer):
    """L6 layer: static AST-based test quality analysis.

    Advisory layer — warns about low-quality test patterns but
    does not block the verification pipeline.
    """
    __test__ = False  # Prevent pytest from collecting this class

    def __init__(self, project_path: str = "."):
        super().__init__()
        self.project_path = project_path

    @property
    def name(self) -> str:
        return "TestQuality"

    @property
    def level(self) -> int:
        return 60

    def run(self, test_files: Optional[List[str]] = None, **kwargs) -> LayerResult:
        """Run static test quality analysis.

        Args:
            test_files: Optional list of test files to analyze.
                        If None, discovers test files in project_path.

        Returns:
            LayerResult with advisory warnings (always passes).
        """
        issues = analyze_test_quality(
            project_path=self.project_path,
            test_files=test_files
        )

        if not issues:
            return LayerResult(
                passed=True,
                message="Test quality: all tests have meaningful assertions"
            )

        # Group by issue type for summary
        by_type = {}
        for issue in issues:
            by_type.setdefault(issue.issue_type, []).append(issue)

        details = []
        for issue_type, items in by_type.items():
            label = issue_type.replace("_", "-")
            details.append(f"  {label}: {len(items)} test(s)")
            for item in items[:5]:  # Show up to 5 per type
                details.append(f"    {item.file}::{item.function} — {item.detail}")
            if len(items) > 5:
                details.append(f"    ... and {len(items) - 5} more")

        return LayerResult(
            passed=True,  # Advisory — never blocks
            message=f"Test quality: {len(issues)} issue(s) found (advisory)",
            error_details=details
        )

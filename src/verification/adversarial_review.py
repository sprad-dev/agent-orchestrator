"""L7: LLM adversarial review layer.

Shells out to `claude --print -p "..."` to get an adversarial analysis
of test quality. Detects issues that static analysis can't catch:
- Hardcoded return values that make tests pass trivially
- Untested error paths
- Missing edge cases
- Tests that don't actually test the behavior they claim to

Advisory by default, opt-in via config (costs tokens).
"""

import subprocess
import os
from typing import List, Optional

from src.verification.layer import Layer, LayerResult, VerificationContext


ADVERSARIAL_PROMPT_TEMPLATE = """You are an adversarial test reviewer. Your job is to find tests that give
false confidence — they pass but don't actually verify correct behavior.

Analyze the following test files and report issues in this exact format.
For each issue, output one line:

ISSUE: <file>::<test_function> — <description>

Look for:
1. Hardcoded return values that make tests pass regardless of implementation correctness
2. Mock-heavy tests that verify call sequences but not actual behavior
3. Tests that don't test what their name claims
4. Missing edge cases (empty inputs, None, boundaries, error conditions)
5. Assertions that are always true regardless of the code under test

If you find no issues, output: NO_ISSUES_FOUND

Test files to review:

{test_content}
"""


def _read_test_files(test_files: List[str], max_chars: int = 50000) -> str:
    """Read and concatenate test file contents with size limit.

    Args:
        test_files: List of test file paths
        max_chars: Maximum total characters to include

    Returns:
        Concatenated file contents with headers
    """
    parts = []
    total = 0
    for filepath in test_files:
        try:
            with open(filepath, "r") as f:
                content = f.read()
        except OSError:
            continue

        header = f"\n--- {filepath} ---\n"
        if total + len(header) + len(content) > max_chars:
            remaining = max_chars - total - len(header) - 50
            if remaining > 100:
                parts.append(header)
                parts.append(content[:remaining])
                parts.append("\n... (truncated)")
            break

        parts.append(header)
        parts.append(content)
        total += len(header) + len(content)

    return "".join(parts)


def _parse_issues(output: str) -> List[str]:
    """Parse ISSUE lines from LLM output.

    Args:
        output: Raw LLM output

    Returns:
        List of issue descriptions
    """
    issues = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("ISSUE:"):
            issues.append(line[6:].strip())
    return issues


def run_adversarial_review(
    test_files: List[str],
    model: str = "sonnet",
    timeout: int = 120
) -> tuple:
    """Run adversarial review using claude CLI.

    Args:
        test_files: List of test file paths to review
        model: Model to use for review
        timeout: Timeout in seconds for the claude CLI call

    Returns:
        Tuple of (issues: List[str], raw_output: str, error: Optional[str])
    """
    if not test_files:
        return [], "", None

    test_content = _read_test_files(test_files)
    if not test_content.strip():
        return [], "", "No test content found"

    prompt = ADVERSARIAL_PROMPT_TEMPLATE.format(test_content=test_content)

    try:
        result = subprocess.run(
            ["claude", "--print", "-m", model, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            return [], result.stderr, f"claude CLI exited with code {result.returncode}"

        output = result.stdout
        issues = _parse_issues(output)
        return issues, output, None

    except FileNotFoundError:
        return [], "", "claude CLI not found on PATH"
    except subprocess.TimeoutExpired:
        return [], "", f"claude CLI timed out after {timeout}s"


class AdversarialReviewLayer(Layer):
    """L7 layer: LLM-powered adversarial test review.

    Shells out to claude CLI for adversarial analysis of test quality.
    Advisory by default. Opt-in since it costs tokens.
    """

    def __init__(self, model: str = "sonnet", timeout: int = 120):
        super().__init__()
        self.model = model
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "AdversarialReview"

    @property
    def level(self) -> int:
        return 70

    def run(self, *, context: 'VerificationContext' = None, test_files: Optional[List[str]] = None, **kwargs) -> LayerResult:
        """Run adversarial review on test files.

        Args:
            context: Optional VerificationContext (test_files read from context)
            test_files: List of test file paths to analyze (overrides context).

        Returns:
            LayerResult with advisory findings (always passes unless strict mode).
        """
        if test_files is None and context is not None:
            test_files = context.test_files
        if not test_files:
            return LayerResult(
                passed=True,
                message="Adversarial review: no test files to analyze"
            )

        issues, raw_output, error = run_adversarial_review(
            test_files, model=self.model, timeout=self.timeout
        )

        if error:
            return LayerResult(
                passed=True,  # Don't block on errors — advisory layer
                message=f"Adversarial review: skipped ({error})",
            )

        if not issues:
            return LayerResult(
                passed=True,
                message="Adversarial review: no issues found"
            )

        details = [f"  {issue}" for issue in issues[:10]]
        if len(issues) > 10:
            details.append(f"  ... and {len(issues) - 10} more")

        return LayerResult(
            passed=True,  # Advisory — never blocks by default
            message=f"Adversarial review: {len(issues)} issue(s) found (advisory)",
            error_details=details
        )

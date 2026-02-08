"""Completion manifest template for agent task verification.

This template forces agents to produce structured proof of completeness
before marking tasks done. Addresses the "hard to spot incompleteness"
failure mode.

Based on Tier 0 backpressure mechanisms from docs/tier0-backpressure-deep-dive.md
"""

COMPLETION_MANIFEST_TEMPLATE = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETION MANIFEST — Required before marking this task complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Files Created
List all new files created for this task:
- [ ] path/to/file1.py — Purpose: ...
- [ ] path/to/file2.py — Purpose: ...
(Or: None)

## Files Modified
List all existing files modified and WHY:
- [ ] path/to/existing.py — Reason: Added X registration, imported Y
- [ ] path/to/config.py — Reason: Updated Z configuration
(Or: None)

## Integration Points
Where does new code connect to existing system?
- [ ] Entrypoint: Exact location where new code is called
      Example: "UserService is called from api/routes.py:42 in create_user()"
- [ ] Registration: Where new code is registered/wired
      Example: "Registered in di/container.py:15"
- [ ] Configuration: Any config changes needed
      Example: "Added DB connection string to appsettings.json"

## Tests Added
Breakdown by type (provide counts):
- [ ] Unit tests: X
      Example: "test_user_service.py: test_create_success, test_create_duplicate"
- [ ] Integration tests: Y
      Example: "test_api_integration.py: test_create_user_endpoint"
- [ ] Edge case/error tests: Z
      Example: "test_user_validation.py: test_null_email, test_invalid_format"
- [ ] Total: X + Y + Z

## Delete Test
"If you deleted [these files], [these tests/behaviors] would fail:"
- [ ] Deleted files: List new files created
- [ ] What breaks: Specific test names or observable behaviors
      Example: "test_api_integration.py::test_create_user would fail with ImportError,
               POST /api/users endpoint would return 404"

## Known Gaps
List anything NOT covered and why:
- [ ] Gap 1: Description and reason (e.g., "Performance optimization deferred to follow-up")
- [ ] Gap 2: ...
(Or: None — all requirements fully met)

## Verification Checklist
Before submitting, verify:
- [ ] All quality gates satisfied (no test-the-mock, no orphan code, etc.)
- [ ] Integration points clearly documented
- [ ] Delete test proves integration
- [ ] Known gaps explicitly listed (empty if complete)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def format_completion_manifest(
    files_created=None,
    files_modified=None,
    integration_points=None,
    tests_added=None,
    delete_test=None,
    known_gaps=None
):
    """Format a completion manifest with provided data.

    Args:
        files_created: List of tuples (filepath, purpose)
        files_modified: List of tuples (filepath, reason)
        integration_points: Dict with keys: entrypoint, registration, configuration
        tests_added: Dict with keys: unit, integration, edge_case (counts or lists)
        delete_test: Dict with keys: deleted_files, what_breaks
        known_gaps: List of gap descriptions

    Returns:
        Formatted completion manifest string
    """
    lines = [
        "━" * 70,
        "COMPLETION MANIFEST",
        "━" * 70,
        "",
    ]

    # Files Created
    lines.append("## Files Created")
    if files_created:
        for filepath, purpose in files_created:
            lines.append(f"- [x] {filepath} — Purpose: {purpose}")
    else:
        lines.append("- None")
    lines.append("")

    # Files Modified
    lines.append("## Files Modified")
    if files_modified:
        for filepath, reason in files_modified:
            lines.append(f"- [x] {filepath} — Reason: {reason}")
    else:
        lines.append("- None")
    lines.append("")

    # Integration Points
    lines.append("## Integration Points")
    if integration_points:
        if 'entrypoint' in integration_points:
            lines.append(f"- [x] Entrypoint: {integration_points['entrypoint']}")
        if 'registration' in integration_points:
            lines.append(f"- [x] Registration: {integration_points['registration']}")
        if 'configuration' in integration_points:
            lines.append(f"- [x] Configuration: {integration_points['configuration']}")
    else:
        lines.append("- No integration points (pure library/utility)")
    lines.append("")

    # Tests Added
    lines.append("## Tests Added")
    if tests_added:
        unit = tests_added.get('unit', 0)
        integration = tests_added.get('integration', 0)
        edge_case = tests_added.get('edge_case', 0)
        total = unit + integration + edge_case

        lines.append(f"- [x] Unit tests: {unit}")
        lines.append(f"- [x] Integration tests: {integration}")
        lines.append(f"- [x] Edge case/error tests: {edge_case}")
        lines.append(f"- [x] Total: {total}")
    else:
        lines.append("- No tests required for this task")
    lines.append("")

    # Delete Test
    lines.append("## Delete Test")
    if delete_test:
        files = delete_test.get('deleted_files', [])
        breaks = delete_test.get('what_breaks', 'Unknown')
        lines.append(f"- [x] Deleted files: {', '.join(files) if files else 'N/A'}")
        lines.append(f"- [x] What breaks: {breaks}")
    else:
        lines.append("- Not applicable (no new files created)")
    lines.append("")

    # Known Gaps
    lines.append("## Known Gaps")
    if known_gaps:
        for gap in known_gaps:
            lines.append(f"- [ ] {gap}")
    else:
        lines.append("- None — all requirements fully met")
    lines.append("")

    # Verification
    lines.append("## Verification Checklist")
    lines.append("- [x] All quality gates satisfied")
    lines.append("- [x] Integration points documented")
    lines.append("- [x] Delete test proves integration")
    lines.append("- [x] Known gaps explicitly listed")
    lines.append("")

    lines.append("━" * 70)

    return '\n'.join(lines)


def parse_completion_manifest(manifest_text):
    """Parse a completion manifest from agent output.

    Args:
        manifest_text: Manifest text from agent

    Returns:
        Dict with parsed manifest data, or None if invalid

    This is useful for automated verification that the manifest
    was actually filled out, not just copy-pasted empty.
    """
    import re

    # Check for critical sections
    required_sections = [
        "Files Created",
        "Files Modified",
        "Integration Points",
        "Tests Added",
        "Delete Test",
        "Known Gaps",
    ]

    parsed = {}
    for section in required_sections:
        if section not in manifest_text:
            return None  # Missing required section

    # Check that it's not just the template (look for checkmarks or actual content)
    if manifest_text.count('[x]') == 0 and manifest_text.count('- None') < 3:
        # Likely just copied template without filling it out
        return None

    # Extract test counts if present
    test_match = re.search(r'Total:\s*(\d+)', manifest_text)
    if test_match:
        parsed['total_tests'] = int(test_match.group(1))

    # Count files created/modified
    files_created = len(re.findall(r'## Files Created.*?- \[x\]', manifest_text, re.DOTALL))
    files_modified = len(re.findall(r'## Files Modified.*?- \[x\]', manifest_text, re.DOTALL))

    parsed['files_created_count'] = files_created
    parsed['files_modified_count'] = files_modified

    return parsed

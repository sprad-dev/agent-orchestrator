"""Tests for prompt templates module."""

import pytest
from src.templates import (
    ANTI_PATTERN_SUFFIX,
    COMPLETION_MANIFEST_TEMPLATE,
    get_quality_gates,
    format_completion_manifest,
)
from src.templates.completion_manifest import parse_completion_manifest


class TestAntiPatternSuffix:
    """Tests for anti-pattern quality gates."""

    def test_suffix_exists(self):
        """Verify suffix is non-empty."""
        assert ANTI_PATTERN_SUFFIX
        assert len(ANTI_PATTERN_SUFFIX) > 100

    def test_suffix_contains_all_gates(self):
        """Verify all 5 quality gates are present."""
        gates = [
            "NO test-the-mock",
            "NO orphan code",
            "NO happy-path-only",
            "NO shallow assertions",
            "WIRING PROOF",
        ]
        for gate in gates:
            assert gate in ANTI_PATTERN_SUFFIX, f"Missing gate: {gate}"

    def test_suffix_has_examples(self):
        """Verify suffix includes BAD/GOOD examples."""
        assert "❌ BAD:" in ANTI_PATTERN_SUFFIX
        assert "✓ GOOD:" in ANTI_PATTERN_SUFFIX

    def test_get_quality_gates_python(self):
        """Test getting quality gates for Python."""
        gates = get_quality_gates('python')
        assert gates
        assert "assert" in gates

    def test_get_quality_gates_csharp(self):
        """Test getting quality gates for C#."""
        gates = get_quality_gates('csharp')
        assert gates
        # Currently returns same template
        assert gates == ANTI_PATTERN_SUFFIX

    def test_get_quality_gates_unknown_language(self):
        """Test getting quality gates for unknown language falls back to default."""
        gates = get_quality_gates('rust')
        assert gates == ANTI_PATTERN_SUFFIX


class TestCompletionManifest:
    """Tests for completion manifest template."""

    def test_template_exists(self):
        """Verify template is non-empty."""
        assert COMPLETION_MANIFEST_TEMPLATE
        assert len(COMPLETION_MANIFEST_TEMPLATE) > 100

    def test_template_contains_all_sections(self):
        """Verify all required sections are present."""
        sections = [
            "Files Created",
            "Files Modified",
            "Integration Points",
            "Tests Added",
            "Delete Test",
            "Known Gaps",
            "Verification Checklist",
        ]
        for section in sections:
            assert section in COMPLETION_MANIFEST_TEMPLATE, f"Missing section: {section}"

    def test_format_manifest_minimal(self):
        """Test formatting manifest with minimal data."""
        manifest = format_completion_manifest()
        assert "Files Created" in manifest
        assert "None" in manifest

    def test_format_manifest_full(self):
        """Test formatting manifest with all data."""
        manifest = format_completion_manifest(
            files_created=[
                ("src/new_module.py", "New feature implementation"),
                ("tests/test_new_module.py", "Tests for new feature"),
            ],
            files_modified=[
                ("src/main.py", "Import and call new module"),
                ("pyproject.toml", "Add new dependency"),
            ],
            integration_points={
                'entrypoint': "Called from main.py:42",
                'registration': "Registered in config.py:15",
            },
            tests_added={
                'unit': 5,
                'integration': 2,
                'edge_case': 3,
            },
            delete_test={
                'deleted_files': ["src/new_module.py"],
                'what_breaks': "test_integration.py::test_feature_x would fail",
            },
            known_gaps=["Performance optimization deferred"],
        )

        assert "src/new_module.py" in manifest
        assert "main.py" in manifest
        assert "Total: 10" in manifest
        assert "Performance optimization deferred" in manifest

    def test_format_manifest_no_tests(self):
        """Test formatting manifest for task with no tests."""
        manifest = format_completion_manifest(
            files_created=[("docs/README.md", "Documentation")],
            tests_added=None,
        )
        assert "No tests required" in manifest

    def test_parse_manifest_valid(self):
        """Test parsing a valid completed manifest."""
        manifest_text = format_completion_manifest(
            files_created=[("src/test.py", "Test")],
            tests_added={'unit': 5, 'integration': 2, 'edge_case': 3},
        )
        parsed = parse_completion_manifest(manifest_text)

        assert parsed is not None
        assert parsed['total_tests'] == 10
        assert parsed['files_created_count'] >= 0

    def test_parse_manifest_empty_template(self):
        """Test parsing detects unfilled template."""
        # Just the template with no checkmarks
        parsed = parse_completion_manifest(COMPLETION_MANIFEST_TEMPLATE)
        assert parsed is None  # Should reject unfilled template

    def test_parse_manifest_missing_sections(self):
        """Test parsing detects missing required sections."""
        incomplete = "## Files Created\n- [x] test.py"
        parsed = parse_completion_manifest(incomplete)
        assert parsed is None  # Missing required sections


class TestIntegration:
    """Integration tests for templates in context building."""

    def test_templates_importable_from_context(self):
        """Verify templates can be imported in context module."""
        from src.context.builder import build_static_context

        context, size = build_static_context([])
        assert ANTI_PATTERN_SUFFIX in context
        assert COMPLETION_MANIFEST_TEMPLATE in context
        assert size > 0

    def test_context_includes_quality_gates(self):
        """Verify built context includes quality gates."""
        from src.context.builder import build_static_context

        context, _ = build_static_context([])
        assert "QUALITY GATES" in context
        assert "NO test-the-mock" in context
        assert "COMPLETION MANIFEST" in context

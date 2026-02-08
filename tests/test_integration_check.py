"""Tests for integration entrypoint verification layer."""

import pytest
from src.verification.integration_check import IntegrationCheckLayer


VALID_MANIFEST = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETION MANIFEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Files Created
- [x] src/new_feature.py — Purpose: Implements new user service

## Files Modified
- [x] src/api/routes.py — Reason: Added endpoint for new feature

## Integration Points
- [x] Entrypoint: Called from src/api/routes.py:42 in create_user()
- [x] Registration: Registered in src/di/container.py:15

## Tests Added
- [x] Unit tests: 5
- [x] Integration tests: 2
- [x] Edge case/error tests: 3
- [x] Total: 10

## Delete Test
- [x] Deleted files: src/new_feature.py
- [x] What breaks: test_api_integration.py::test_create_user would fail with ImportError

## Known Gaps
- None — all requirements fully met

## Verification Checklist
- [x] All quality gates satisfied
- [x] Integration points documented
- [x] Delete test proves integration
- [x] Known gaps explicitly listed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


TEMPLATE_ONLY_MANIFEST = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETION MANIFEST — Required before marking this task complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Files Created
List all new files created for this task:
- [ ] path/to/file1.py — Purpose: ...

## Files Modified
List all existing files modified and WHY:
- [ ] path/to/existing.py — Reason: Added X registration

## Integration Points
Where does new code connect to existing system?
- [ ] Entrypoint: Exact location where new code is called

## Tests Added
Breakdown by type (provide counts):
- [ ] Unit tests: X

## Delete Test
"If you deleted [these files], [these tests/behaviors] would fail:"
- [ ] Deleted files: List new files created
- [ ] What breaks: Specific test names or observable behaviors

## Known Gaps
List anything NOT covered and why:
(Or: None — all requirements fully met)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


MANIFEST_MISSING_INTEGRATION = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETION MANIFEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Files Created
- [x] src/orphan_code.py — Purpose: New utility function

## Files Modified
- None

## Integration Points
- No integration points (pure library/utility)

## Tests Added
- [x] Unit tests: 3
- [x] Total: 3

## Delete Test
- Not applicable (no new files created)

## Known Gaps
- None

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


MANIFEST_WITH_PLACEHOLDER_DELETE_TEST = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETION MANIFEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Files Created
- [x] src/new_module.py — Purpose: Feature implementation

## Files Modified
- [x] src/main.py — Reason: Import new module

## Integration Points
- [x] Entrypoint: Called from src/main.py

## Tests Added
- [x] Unit tests: 5
- [x] Total: 5

## Delete Test
- [x] Deleted files: src/new_module.py
- [x] What breaks: [these tests/behaviors] would fail

## Known Gaps
- None

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


class TestIntegrationCheckLayer:
    """Tests for IntegrationCheckLayer."""

    def test_name_and_level(self):
        """Test layer name and level properties."""
        layer = IntegrationCheckLayer()
        assert layer.name == "IntegrationCheck"
        assert layer.level == 4

    def test_valid_manifest_passes(self):
        """Test that a properly filled manifest passes."""
        layer = IntegrationCheckLayer()
        result = layer.run(manifest_text=VALID_MANIFEST)

        assert result.passed is True
        assert "properly integrated" in result.message.lower()

    def test_template_only_manifest_fails(self):
        """Test that a template-only manifest fails."""
        layer = IntegrationCheckLayer()
        result = layer.run(manifest_text=TEMPLATE_ONLY_MANIFEST)

        assert result.passed is False
        assert "invalid or empty" in result.message.lower()
        assert len(result.error_details) > 0

    def test_orphaned_code_fails(self):
        """Test that orphaned code (no integration) fails."""
        layer = IntegrationCheckLayer()
        result = layer.run(manifest_text=MANIFEST_MISSING_INTEGRATION)

        assert result.passed is False
        # Should fail because delete test says "not applicable" but files were created
        assert any("delete test" in detail.lower() for detail in result.error_details)

    def test_placeholder_delete_test_fails(self):
        """Test that placeholder text in delete test fails."""
        layer = IntegrationCheckLayer()
        result = layer.run(manifest_text=MANIFEST_WITH_PLACEHOLDER_DELETE_TEST)

        assert result.passed is False
        assert any("placeholder" in detail.lower() for detail in result.error_details)

    def test_no_manifest_no_new_files_passes(self):
        """Test that modifications-only (no new files) passes without manifest."""
        layer = IntegrationCheckLayer()

        # Mock _get_new_files to return empty list
        layer._get_new_files = lambda: []

        result = layer.run(manifest_text=None)

        assert result.passed is True
        assert "modifications only" in result.message.lower()

    def test_extract_section(self):
        """Test section extraction from manifest."""
        layer = IntegrationCheckLayer()

        section = layer._extract_section(VALID_MANIFEST, "Integration Points")
        assert section is not None
        assert "Entrypoint" in section
        assert "routes.py:42" in section

    def test_extract_section_missing(self):
        """Test section extraction when section doesn't exist."""
        layer = IntegrationCheckLayer()

        section = layer._extract_section(VALID_MANIFEST, "Nonexistent Section")
        assert section is None

    def test_strict_mode_validates_entrypoints(self, tmp_path):
        """Test that strict mode validates entrypoint file existence."""
        import os

        # Create a test file
        test_file = tmp_path / "test_routes.py"
        test_file.write_text("def create_user():\n    pass\n")

        # Change to temp directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Create manifest with valid file path
            manifest = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETION MANIFEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Files Created
- [x] new_feature.py — Purpose: Feature

## Files Modified
- [x] test_routes.py — Reason: Integration

## Integration Points
- [x] Entrypoint: Called from test_routes.py:1

## Tests Added
- [x] Total: 5

## Delete Test
- [x] Deleted files: new_feature.py
- [x] What breaks: Tests fail

## Known Gaps
- None

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

            layer = IntegrationCheckLayer(strict_mode=True)
            result = layer.run(manifest_text=manifest)

            assert result.passed is True
        finally:
            os.chdir(original_cwd)

    def test_strict_mode_fails_on_missing_file(self):
        """Test that strict mode fails when entrypoint file doesn't exist."""
        manifest = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETION MANIFEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Files Created
- [x] new_feature.py — Purpose: Feature

## Files Modified
- [x] nonexistent.py — Reason: Integration

## Integration Points
- [x] Entrypoint: Called from nonexistent.py:42

## Tests Added
- [x] Total: 5

## Delete Test
- [x] Deleted files: new_feature.py
- [x] What breaks: Tests fail

## Known Gaps
- None

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        layer = IntegrationCheckLayer(strict_mode=True)
        result = layer.run(manifest_text=manifest)

        assert result.passed is False
        assert any("not found" in detail.lower() for detail in result.error_details)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

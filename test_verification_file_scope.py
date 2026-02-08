"""Tests for L2 file scope validation."""

import pytest
import tempfile
import os
from pathlib import Path
from src.verification.file_scope import FileScopeLayer
from src.shell import run_shell


@pytest.fixture
def git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_dir = os.getcwd()
        os.chdir(tmpdir)

        # Initialize git repo
        run_shell("git init", ignore_error=True)
        run_shell("git config user.email 'test@test.com'", ignore_error=True)
        run_shell("git config user.name 'Test'", ignore_error=True)

        # Create initial files and commit
        Path("src/main.py").parent.mkdir(parents=True, exist_ok=True)
        Path("src/main.py").write_text("# main\n")
        Path("tests/test_main.py").parent.mkdir(parents=True, exist_ok=True)
        Path("tests/test_main.py").write_text("# test\n")
        Path("config.yaml").write_text("# config\n")

        run_shell("git add .", ignore_error=True)
        run_shell("git commit -m 'Initial commit'", ignore_error=True)

        yield tmpdir

        os.chdir(original_dir)


def test_no_restrictions_allows_all(git_repo):
    """When no allowed_patterns set, all files should be allowed."""
    # Modify a file
    Path("src/main.py").write_text("# modified\n")

    layer = FileScopeLayer(allowed_patterns=None)
    result = layer.run()

    assert result.passed is True
    assert "unrestricted" in result.message


def test_no_changes_passes(git_repo):
    """When no files changed, should pass."""
    layer = FileScopeLayer(allowed_patterns=["src/**/*.py"])
    result = layer.run()

    assert result.passed is True
    assert "No files changed" in result.message


def test_allowed_file_passes(git_repo):
    """Modifying a file matching allowed pattern should pass."""
    # Modify allowed file
    Path("src/main.py").write_text("# modified\n")

    layer = FileScopeLayer(allowed_patterns=["src/**/*.py", "tests/**/*.py"])
    result = layer.run()

    assert result.passed is True
    assert "File scope valid" in result.message


def test_unauthorized_file_blocked(git_repo):
    """Modifying file outside allowed scope should fail."""
    # Modify unauthorized file
    Path("config.yaml").write_text("# modified config\n")

    layer = FileScopeLayer(allowed_patterns=["src/**/*.py", "tests/**/*.py"])
    result = layer.run()

    assert result.passed is False
    assert "outside allowed scope" in result.message
    assert "config.yaml" in str(result.error_details)


def test_multiple_files_mixed(git_repo):
    """Mix of allowed and unauthorized files should fail."""
    # Modify both allowed and unauthorized
    Path("src/main.py").write_text("# modified main\n")
    Path("config.yaml").write_text("# modified config\n")

    layer = FileScopeLayer(allowed_patterns=["src/**/*.py"])
    result = layer.run()

    assert result.passed is False
    assert "config.yaml" in str(result.error_details)


def test_wildcard_patterns(git_repo):
    """Wildcard patterns should work correctly."""
    # Modify existing file (not create new, to avoid git tracking issues)
    Path("src/main.py").write_text("# modified utils\n")

    layer = FileScopeLayer(allowed_patterns=["src/*.py"])
    result = layer.run()

    assert result.passed is True
    assert "File scope valid" in result.message


def test_specific_file_pattern(git_repo):
    """Specific file patterns should work."""
    # Modify specific allowed file
    Path("config.yaml").write_text("# modified\n")

    layer = FileScopeLayer(allowed_patterns=["config.yaml"])
    result = layer.run()

    assert result.passed is True
    assert "File scope valid" in result.message

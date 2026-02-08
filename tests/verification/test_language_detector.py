"""Tests for language detection."""

import pytest
from pathlib import Path
import tempfile
import shutil
from src.verification.language_detector import (
    Language,
    detect_language,
    detect_languages_in_files,
    _detect_from_extensions
)


class TestLanguageDetection:
    """Test language detection from project files."""

    def test_detect_python_from_setup_py(self, tmp_path):
        """Detect Python from setup.py."""
        (tmp_path / "setup.py").touch()
        assert detect_language(str(tmp_path)) == Language.PYTHON

    def test_detect_python_from_pyproject_toml(self, tmp_path):
        """Detect Python from pyproject.toml."""
        (tmp_path / "pyproject.toml").touch()
        assert detect_language(str(tmp_path)) == Language.PYTHON

    def test_detect_python_from_requirements_txt(self, tmp_path):
        """Detect Python from requirements.txt."""
        (tmp_path / "requirements.txt").touch()
        assert detect_language(str(tmp_path)) == Language.PYTHON

    def test_detect_typescript_from_tsconfig(self, tmp_path):
        """Detect TypeScript from tsconfig.json."""
        (tmp_path / "tsconfig.json").touch()
        assert detect_language(str(tmp_path)) == Language.TYPESCRIPT

    def test_detect_javascript_from_package_json(self, tmp_path):
        """Detect JavaScript from package.json."""
        (tmp_path / "package.json").touch()
        assert detect_language(str(tmp_path)) == Language.JAVASCRIPT

    def test_typescript_priority_over_javascript(self, tmp_path):
        """TypeScript detection takes priority over JavaScript."""
        (tmp_path / "package.json").touch()
        (tmp_path / "tsconfig.json").touch()
        # TypeScript should win due to priority order
        assert detect_language(str(tmp_path)) == Language.TYPESCRIPT

    def test_detect_unknown_for_empty_directory(self, tmp_path):
        """Detect UNKNOWN for empty directory."""
        assert detect_language(str(tmp_path)) == Language.UNKNOWN

    def test_detect_unknown_for_nonexistent_path(self):
        """Detect UNKNOWN for nonexistent path."""
        assert detect_language("/nonexistent/path") == Language.UNKNOWN


class TestDetectFromExtensions:
    """Test fallback detection from file extensions."""

    def test_detect_python_from_py_files(self, tmp_path):
        """Detect Python from .py files."""
        (tmp_path / "main.py").touch()
        (tmp_path / "utils.py").touch()
        assert _detect_from_extensions(tmp_path) == Language.PYTHON

    def test_detect_javascript_from_js_files(self, tmp_path):
        """Detect JavaScript from .js files."""
        (tmp_path / "index.js").touch()
        (tmp_path / "app.js").touch()
        assert _detect_from_extensions(tmp_path) == Language.JAVASCRIPT

    def test_detect_typescript_from_ts_files(self, tmp_path):
        """Detect TypeScript from .ts files."""
        (tmp_path / "main.ts").touch()
        (tmp_path / "types.ts").touch()
        assert _detect_from_extensions(tmp_path) == Language.TYPESCRIPT

    def test_detect_most_common_language(self, tmp_path):
        """Detect language with most files."""
        (tmp_path / "one.py").touch()
        (tmp_path / "two.js").touch()
        (tmp_path / "three.js").touch()
        # JavaScript wins (2 files vs 1)
        assert _detect_from_extensions(tmp_path) == Language.JAVASCRIPT

    def test_detect_unknown_when_no_files(self, tmp_path):
        """Detect UNKNOWN when no source files."""
        assert _detect_from_extensions(tmp_path) == Language.UNKNOWN


class TestDetectLanguagesInFiles:
    """Test language detection from file list."""

    def test_detect_python_from_py_files(self):
        """Detect Python from .py file paths."""
        files = ["main.py", "utils.py"]
        assert detect_languages_in_files(files) == [Language.PYTHON]

    def test_detect_javascript_from_js_files(self):
        """Detect JavaScript from .js file paths."""
        files = ["index.js", "app.jsx"]
        assert detect_languages_in_files(files) == [Language.JAVASCRIPT]

    def test_detect_typescript_from_ts_files(self):
        """Detect TypeScript from .ts file paths."""
        files = ["main.ts", "types.tsx"]
        assert detect_languages_in_files(files) == [Language.TYPESCRIPT]

    def test_detect_multiple_languages(self):
        """Detect multiple languages from mixed files."""
        files = ["main.py", "app.js", "types.ts"]
        languages = detect_languages_in_files(files)
        # Should preserve order encountered
        assert languages == [Language.PYTHON, Language.JAVASCRIPT, Language.TYPESCRIPT]

    def test_deduplicate_languages(self):
        """Deduplicate repeated languages."""
        files = ["one.py", "two.py", "three.js", "four.js"]
        languages = detect_languages_in_files(files)
        assert languages == [Language.PYTHON, Language.JAVASCRIPT]

    def test_detect_unknown_for_empty_list(self):
        """Detect UNKNOWN for empty file list."""
        assert detect_languages_in_files([]) == [Language.UNKNOWN]

    def test_detect_unknown_for_unrecognized_extensions(self):
        """Detect UNKNOWN for unrecognized file extensions."""
        files = ["README.md", "data.txt"]
        assert detect_languages_in_files(files) == [Language.UNKNOWN]

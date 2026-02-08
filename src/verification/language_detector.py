"""Language detection for project analysis.

Auto-detects programming language from project structure and files.
Used to select appropriate verification validators.
"""

from enum import Enum
from pathlib import Path
from typing import Optional, List


class Language(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


# Language detection patterns (file existence and priority order)
DETECTION_PATTERNS = [
    # TypeScript (check before JavaScript since TS projects often have package.json)
    (Language.TYPESCRIPT, ["tsconfig.json"]),

    # JavaScript/Node.js
    (Language.JAVASCRIPT, ["package.json", "package-lock.json", "yarn.lock"]),

    # Python
    (Language.PYTHON, ["setup.py", "pyproject.toml", "requirements.txt", "Pipfile"]),

    # Go
    (Language.GO, ["go.mod", "go.sum"]),

    # Rust
    (Language.RUST, ["Cargo.toml", "Cargo.lock"]),
]


def detect_language(project_path: str = ".") -> Language:
    """Detect project language from file markers.

    Checks for characteristic files in order of specificity.
    Returns first match or UNKNOWN.

    Args:
        project_path: Path to project root (default: current directory)

    Returns:
        Language enum value
    """
    root = Path(project_path)

    if not root.exists():
        return Language.UNKNOWN

    # Check each pattern in priority order
    for language, patterns in DETECTION_PATTERNS:
        for pattern in patterns:
            if (root / pattern).exists():
                return language

    # Fallback: check file extensions
    return _detect_from_extensions(root)


def _detect_from_extensions(root: Path) -> Language:
    """Detect language from source file extensions.

    Fallback method when no config files found.
    Counts files by extension and returns most common.

    Args:
        root: Project root path

    Returns:
        Language enum value
    """
    extension_counts = {
        ".py": Language.PYTHON,
        ".js": Language.JAVASCRIPT,
        ".ts": Language.TYPESCRIPT,
        ".go": Language.GO,
        ".rs": Language.RUST,
    }

    counts = {lang: 0 for lang in extension_counts.values()}

    # Count files (shallow search - top 2 levels to avoid traversing node_modules, etc.)
    for depth in range(2):
        pattern = "*/" * depth + "*"
        for ext, lang in extension_counts.items():
            matching_files = list(root.glob(pattern + ext))
            counts[lang] += len(matching_files)

    # Return language with most files
    max_count = max(counts.values())
    if max_count == 0:
        return Language.UNKNOWN

    for lang, count in counts.items():
        if count == max_count:
            return lang

    return Language.UNKNOWN


def detect_languages_in_files(files: List[str]) -> List[Language]:
    """Detect languages from a list of file paths.

    Useful for determining which validators to run on specific files.

    Args:
        files: List of file paths

    Returns:
        List of detected languages (unique, in order encountered)
    """
    extension_map = {
        ".py": Language.PYTHON,
        ".js": Language.JAVASCRIPT,
        ".jsx": Language.JAVASCRIPT,
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
        ".go": Language.GO,
        ".rs": Language.RUST,
    }

    detected = []
    seen = set()

    for file_path in files:
        ext = Path(file_path).suffix
        lang = extension_map.get(ext, Language.UNKNOWN)

        if lang != Language.UNKNOWN and lang not in seen:
            detected.append(lang)
            seen.add(lang)

    return detected if detected else [Language.UNKNOWN]

"""Context file parsing, loading, and building for prompt optimization.

This module handles:
- Parsing context_files from task specifications (JSON or inline format)
- Inferring context files from task descriptions
- Loading file contents into formatted context strings
- Building static context optimized for prompt caching
"""

import os
import json
import re
from pathlib import Path
from src.templates import ANTI_PATTERN_SUFFIX, COMPLETION_MANIFEST_TEMPLATE


def parse_context_files(task):
    """Parse context_files from task specification.
    
    Supports two formats:
    1. JSON-like: context_files: ["file1.py", "file2.py"]
    2. Inline marker: [context: file1.py, file2.py]
    
    Returns list of file paths or None if not specified.
    """
    # Try JSON-like format
    match = re.search(r'context_files:\s*\[([^\]]+)\]', task)
    if match:
        files_str = match.group(1)
        # Parse as JSON array or comma-separated
        try:
            files = json.loads('[' + files_str + ']')
            return [f.strip().strip('"\'') for f in files if f.strip()]
        except json.JSONDecodeError:
            # Fallback to comma-separated
            return [f.strip().strip('"\'') for f in files_str.split(',') if f.strip()]
    
    # Try inline marker format
    match = re.search(r'\[context:\s*([^\]]+)\]', task)
    if match:
        files_str = match.group(1)
        return [f.strip() for f in files_str.split(',') if f.strip()]
    
    return None


def get_default_context_files(task):
    """Infer context files from task description.
    
    Looks for Python file mentions and includes corresponding test files.
    Returns list of file paths.
    """
    files = []
    
    # Find Python file mentions in task
    py_files = re.findall(r'\b(\w+\.py)\b', task)
    for f in py_files:
        if os.path.exists(f):
            files.append(f)
            # Add corresponding test file if it exists
            test_file = f'test_{f}'
            if os.path.exists(test_file):
                files.append(test_file)
    
    return list(set(files))  # Remove duplicates


def build_context(files):
    """Load specified files and build context string.
    
    Returns formatted context with file contents.
    """
    if not files:
        return ""
    
    context_parts = ["\n=== CONTEXT FILES ===\n"]
    
    # Get the project root directory for path validation
    try:
        project_root = os.path.abspath(os.getcwd())
    except Exception:
        project_root = os.path.abspath('.')
    
    for filepath in files:
        # Validate path to prevent path traversal
        if filepath.startswith('/') or '..' in filepath:
            context_parts.append(f"\n--- {filepath} (INVALID PATH) ---\n")
            continue
        
        # Resolve to absolute path and verify it's within project directory
        try:
            abs_path = os.path.abspath(filepath)
            if not abs_path.startswith(project_root):
                context_parts.append(f"\n--- {filepath} (PATH OUTSIDE PROJECT) ---\n")
                continue
        except Exception:
            context_parts.append(f"\n--- {filepath} (INVALID PATH) ---\n")
            continue
        
        if not os.path.exists(filepath):
            context_parts.append(f"\n--- {filepath} (NOT FOUND) ---\n")
            continue
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            context_parts.append(f"\n--- {filepath} ---\n{content}\n")
        except Exception as e:
            context_parts.append(f"\n--- {filepath} (ERROR: {e}) ---\n")
    
    context_parts.append("=== END CONTEXT ===\n")
    return ''.join(context_parts)


def build_static_context(context_files):
    """Build static context block optimized for prompt caching.

    CACHING STRATEGY:
    Claude's automatic prompt caching caches long prefixes. By placing
    static content (repo files, docs) at the beginning, subsequent
    retries can reuse the cached context at ~90% cost reduction.

    This method returns the static portion that should appear first
    in prompts to maximize cache hit rates.

    Quality gates and completion manifest are ALWAYS included, even
    without context files, as they are core Tier 0 backpressure mechanisms.

    Returns: tuple of (static_context_str, context_size_bytes)
    """
    static_parts = []

    # Repository structure/context files - these are stable across retries
    if context_files:
        file_context = build_context(context_files)
        if file_context:
            static_parts.append(file_context)

    # Quality gates and completion requirements (Tier 0 backpressure)
    # ALWAYS include these, even without context files
    static_parts.append(ANTI_PATTERN_SUFFIX)
    static_parts.append("\n")
    static_parts.append(COMPLETION_MANIFEST_TEMPLATE)

    static_content = ''.join(static_parts)
    return static_content, len(static_content.encode('utf-8'))

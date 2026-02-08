"""Prompt templates for agent quality gates and completion verification.

This module provides reusable templates for:
- Anti-pattern suffixes appended to task prompts
- Completion manifests required before marking tasks done

All templates are designed to work across Python, .NET, and TypeScript projects.
"""

from .quality_gates import ANTI_PATTERN_SUFFIX, get_quality_gates
from .completion_manifest import COMPLETION_MANIFEST_TEMPLATE, format_completion_manifest

__all__ = [
    'ANTI_PATTERN_SUFFIX',
    'get_quality_gates',
    'COMPLETION_MANIFEST_TEMPLATE',
    'format_completion_manifest',
]

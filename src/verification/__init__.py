"""Verification pipeline module.

Multi-layer verification checks:
- L1: File exists check
- L2: Syntax validation (language-specific), File scope verification
- L3: Test execution, count verification, and coverage (language-specific)
- L4: Integration verification (entrypoint reachability, delete test)
- L5: Human approval gate

Supports Python, TypeScript/JavaScript, and .NET/C# projects.
"""

from .runner import VerificationRunner
from .file_exists import validate_files_exist
from .performance_metrics import PerformanceTracker, MetricsData
from .config import VerificationConfig, load_config, save_config
from .integration_check import IntegrationCheckLayer
from .file_scope import FileScopeLayer
from .language_detector import Language, detect_language, detect_languages_in_files
from .validator_factory import ValidatorFactory

__all__ = [
    "VerificationRunner",
    "validate_files_exist",
    "PerformanceTracker",
    "MetricsData",
    "VerificationConfig",
    "load_config",
    "save_config",
    "IntegrationCheckLayer",
    "FileScopeLayer",
    "Language",
    "detect_language",
    "detect_languages_in_files",
    "ValidatorFactory",
]

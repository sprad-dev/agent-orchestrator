"""Verification pipeline module.

Multi-layer verification checks:
- L1: File exists check
- L2: Syntax validation (py_compile), File scope verification
- L3: Test execution, count verification, and coverage
- L4: Integration verification (entrypoint reachability, delete test)
- L5: Human approval gate
"""

from .runner import VerificationRunner
from .file_exists import validate_files_exist
from .performance_metrics import PerformanceTracker, MetricsData
from .config import VerificationConfig, load_config, save_config
from .integration_check import IntegrationCheckLayer
from .file_scope import FileScopeLayer

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
]

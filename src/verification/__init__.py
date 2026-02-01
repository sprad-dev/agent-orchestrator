"""Verification pipeline module.

Multi-layer verification checks:
- L1: File exists check
- L2: Syntax validation (py_compile)
- L3: Test execution and count verification
- L4: Regression detection
- L5: Human approval gate
"""

from .runner import VerificationRunner

__all__ = [
    "VerificationRunner",
]

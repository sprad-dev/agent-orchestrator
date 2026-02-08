"""L1: File existence validation.

Checks that files exist before running verification layers.
Provides clear error messages for missing files to prevent downstream failures.
"""

from pathlib import Path
from typing import List, Tuple
from src.verification.layer import Layer, LayerResult, VerificationContext


class FileExistsLayer(Layer):
    """L1: File existence validation layer."""
    
    def __init__(self):
        """Initialize file exists layer."""
        super().__init__()
    
    @property
    def name(self) -> str:
        """Layer name."""
        return "FileExists"
    
    @property
    def level(self) -> int:
        """Layer level (L1)."""
        return 1
    
    def run(self, *, context: 'VerificationContext' = None, files: List[str] = None, **kwargs) -> LayerResult:
        """Validate that files exist.

        Args:
            context: Optional VerificationContext (files read from context.modified_files)
            files: List of file paths to check (overrides context)
            **kwargs: Ignored (for compatibility)

        Returns:
            LayerResult with validation status
        """
        if files is None and context is not None:
            files = context.modified_files
        if not files:
            return LayerResult(
                passed=True,
                message="No files to validate"
            )
        
        errors = []
        
        for file_path in files:
            path = Path(file_path)
            
            try:
                if not path.exists():
                    errors.append(f"File not found: {file_path}")
            except (OSError, PermissionError) as e:
                errors.append(f"Cannot access file {file_path}: {str(e)}")
        
        if errors:
            return LayerResult(
                passed=False,
                message="File existence check failed",
                error_details=errors
            )
        
        return LayerResult(
            passed=True,
            message=f"All {len(files)} file(s) exist"
        )


def validate_files_exist(files: List[str]) -> Tuple[bool, List[str]]:
    """Validate that all specified files exist.
    
    Deprecated: Use FileExistsLayer.run() instead.
    Kept for backwards compatibility.
    
    Args:
        files: List of file paths to check
        
    Returns:
        Tuple of (all_exist, error_messages)
        - all_exist: True if all files exist
        - error_messages: List of error messages for missing files
    """
    layer = FileExistsLayer()
    result = layer.run(files=files)
    return result.passed, result.error_details

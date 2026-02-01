"""L2: Python syntax validation using py_compile.

Fast syntax checking (~1ms per file) before running pytest.
Provides immediate feedback on parse errors.
"""

import py_compile
from pathlib import Path
from typing import List, Tuple
from src.verification.layer import Layer, LayerResult


class SyntaxCheckLayer(Layer):
    """L2: Python syntax validation layer."""
    
    def __init__(self):
        """Initialize syntax check layer."""
        super().__init__()
    
    @property
    def name(self) -> str:
        """Layer name."""
        return "SyntaxCheck"
    
    @property
    def level(self) -> int:
        """Layer level (L2)."""
        return 2
    
    def run(self, files: List[str] = None, **kwargs) -> LayerResult:
        """Validate Python syntax on files.
        
        Args:
            files: List of file paths to check
            **kwargs: Ignored (for compatibility)
            
        Returns:
            LayerResult with validation status
        """
        if not files:
            return LayerResult(
                passed=True,
                message="No files to validate"
            )
        
        errors = []
        
        for file_path in files:
            path = Path(file_path)
            
            # Skip non-Python files
            if not path.suffix == '.py':
                continue
                
            # Skip if file doesn't exist
            if not path.exists():
                continue
                
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"{file_path}: {e.msg}")
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")
        
        if errors:
            return LayerResult(
                passed=False,
                message="Syntax check failed",
                error_details=errors
            )
        
        return LayerResult(
            passed=True,
            message=f"Python syntax valid for all files"
        )


def validate_python_syntax(files: List[str]) -> Tuple[bool, List[str]]:
    """Validate Python syntax on list of files.
    
    Deprecated: Use SyntaxCheckLayer.run() instead.
    Kept for backwards compatibility.
    
    Args:
        files: List of file paths to check
        
    Returns:
        Tuple of (all_valid, error_messages)
        - all_valid: True if all files have valid syntax
        - error_messages: List of error messages for failed files
    """
    layer = SyntaxCheckLayer()
    result = layer.run(files=files)
    return result.passed, result.error_details

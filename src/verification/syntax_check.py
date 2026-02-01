"""L2: Python syntax validation using py_compile.

Fast syntax checking (~1ms per file) before running pytest.
Provides immediate feedback on parse errors.
"""

import py_compile
from pathlib import Path
from typing import List, Tuple


def validate_python_syntax(files: List[str]) -> Tuple[bool, List[str]]:
    """Validate Python syntax on list of files.
    
    Args:
        files: List of file paths to check
        
    Returns:
        Tuple of (all_valid, error_messages)
        - all_valid: True if all files have valid syntax
        - error_messages: List of error messages for failed files
    """
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
    
    return len(errors) == 0, errors

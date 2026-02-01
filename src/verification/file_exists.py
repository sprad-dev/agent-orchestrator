"""L1: File existence validation.

Checks that files exist before running verification layers.
Provides clear error messages for missing files to prevent downstream failures.
"""

from pathlib import Path
from typing import List, Tuple


def validate_files_exist(files: List[str]) -> Tuple[bool, List[str]]:
    """Validate that all specified files exist.
    
    Args:
        files: List of file paths to check
        
    Returns:
        Tuple of (all_exist, error_messages)
        - all_exist: True if all files exist
        - error_messages: List of error messages for missing files
    """
    errors = []
    
    for file_path in files:
        path = Path(file_path)
        
        try:
            if not path.exists():
                errors.append(f"File not found: {file_path}")
        except (OSError, PermissionError) as e:
            errors.append(f"Cannot access file {file_path}: {str(e)}")
    
    return len(errors) == 0, errors

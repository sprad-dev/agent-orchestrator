"""Commit guard for pre-commit safety checks.

This module orchestrates commit guards.
Individual guards are implemented as separate functions/classes
to enable parallel development.
"""

import re
import shlex
from typing import List, Tuple, Set
from src.shell import run_shell, get_diff_content


from typing import Optional
from dataclasses import dataclass


@dataclass
class GuardResult:
    """Result from a guard check."""
    name: str
    passed: bool
    issues: List[str]
    priority: int = 100


class Guard:
    """Base class for commit guards."""
    
    def __init__(self, name: str, priority: int = 100, enabled: bool = True):
        """Initialize guard.
        
        Args:
            name: Guard identifier
            priority: Execution priority (lower runs first)
            enabled: Whether guard is active
        """
        self.name = name
        self.priority = priority
        self.enabled = enabled
    
    def check(self) -> GuardResult:
        """Execute guard check.
        
        Returns:
            GuardResult with check outcome
        """
        raise NotImplementedError("Subclasses must implement check()")


class GuardRegistry:
    """Registry for managing and executing commit guards."""
    
    def __init__(self):
        """Initialize empty registry."""
        self._guards: List[Guard] = []
    
    def register(self, guard: Guard) -> None:
        """Add guard to registry.
        
        Args:
            guard: Guard instance to register
        """
        self._guards.append(guard)
    
    def unregister(self, name: str) -> bool:
        """Remove guard from registry.
        
        Args:
            name: Name of guard to remove
            
        Returns:
            True if guard was found and removed
        """
        original_len = len(self._guards)
        self._guards = [g for g in self._guards if g.name != name]
        return len(self._guards) < original_len
    
    def enable(self, name: str) -> bool:
        """Enable a specific guard.
        
        Args:
            name: Name of guard to enable
            
        Returns:
            True if guard was found
        """
        for guard in self._guards:
            if guard.name == name:
                guard.enabled = True
                return True
        return False
    
    def disable(self, name: str) -> bool:
        """Disable a specific guard.
        
        Args:
            name: Name of guard to disable
            
        Returns:
            True if guard was found
        """
        for guard in self._guards:
            if guard.name == name:
                guard.enabled = False
                return True
        return False
    
    def get_guard(self, name: str) -> Optional[Guard]:
        """Get guard by name.
        
        Args:
            name: Guard name
            
        Returns:
            Guard instance or None if not found
        """
        for guard in self._guards:
            if guard.name == name:
                return guard
        return None
    
    def list_guards(self) -> List[Guard]:
        """Get all registered guards.
        
        Returns:
            List of all guards
        """
        return self._guards.copy()
    
    def execute_all(self, short_circuit: bool = True) -> Tuple[bool, List[GuardResult]]:
        """Execute all enabled guards in priority order.
        
        Args:
            short_circuit: Stop on first failure if True
            
        Returns:
            Tuple of (all_passed, results)
        """
        # Sort guards by priority (lower priority runs first)
        enabled_guards = [g for g in self._guards if g.enabled]
        sorted_guards = sorted(enabled_guards, key=lambda g: g.priority)
        
        results = []
        all_passed = True
        
        for guard in sorted_guards:
            result = guard.check()
            results.append(result)
            
            if not result.passed:
                all_passed = False
                if short_circuit:
                    break
        
        return all_passed, results



class CommitGuard:
    """Guards commits with safety checks."""

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {
        '.py', '.txt', '.md', '.json', '.yaml', '.yml', 
        '.toml', '.ini', '.sh', '.rst', '.cfg'
    }
    
    # Binary file extensions (blocked)
    BINARY_EXTENSIONS = {
        # Executables
        '.exe', '.dll', '.so', '.dylib', '.bin',
        # Compiled
        '.o', '.obj', '.pyc', '.class', '.jar',
        # Archives
        '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar',
        # Images
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
        # Media
        '.mp3', '.mp4', '.avi', '.mov', '.wav',
        # Documents
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        # Others
        '.db', '.sqlite', '.dat'
    }

    # Secret detection patterns
    SECRET_PATTERNS = {
        'aws_access_key': r'AKIA[0-9A-Z]{16}',
        'aws_secret_key': r'[A-Za-z0-9/+=]{40}',
        'bearer_token': r'Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+',
        'openai_key': r'sk-[A-Za-z0-9]{20,}',
        'github_pat': r'ghp_[A-Za-z0-9]{36}',
        'github_oauth': r'gho_[A-Za-z0-9]{36}',
        'private_key_rsa': r'-----BEGIN RSA PRIVATE KEY-----',
        'private_key_dsa': r'-----BEGIN DSA PRIVATE KEY-----',
        'private_key_ec': r'-----BEGIN EC PRIVATE KEY-----',
        'private_key_openssh': r'-----BEGIN OPENSSH PRIVATE KEY-----',
        'generic_password': r'["\']password["\']\s*:\s*["\'][^"\']{8,}["\']',
        'generic_api_key': r'["\']api[_\-]?key["\']\s*:\s*["\'][A-Za-z0-9]{32,}["\']',
    }

    def __init__(self, allowed_extensions: Set[str] = None, blocked_extensions: Set[str] = None):
        """Initialize commit guard.
        
        Args:
            allowed_extensions: Set of allowed file extensions (overrides defaults)
            blocked_extensions: Set of blocked file extensions (overrides defaults)
        """
        self.allowed_extensions = allowed_extensions if allowed_extensions is not None else self.ALLOWED_EXTENSIONS
        self.blocked_extensions = blocked_extensions if blocked_extensions is not None else self.BINARY_EXTENSIONS
        self.registry = GuardRegistry()

    def check_all(self) -> Tuple[bool, List[str]]:
        """Run all commit guards.

        Returns:
            Tuple of (passed: bool, issues: list)
        """
        # If registry has guards, use it
        if len(self.registry.list_guards()) > 0:
            passed, results = self.registry.execute_all(short_circuit=True)
            
            # Aggregate issues from all results
            issues = []
            for result in results:
                if not result.passed:
                    issues.extend(result.issues)
            
            return passed, issues
        
        # Fallback: Run built-in checks directly (backward compatibility)
        all_issues = []
        
        # Check secrets
        passed, issues = self.check_secrets()
        all_issues.extend(issues)
        
        # Check file types
        passed_ft, issues_ft = self.check_file_types()
        all_issues.extend(issues_ft)
        passed = passed and passed_ft
        
        return passed, all_issues

    def check_secrets(self) -> Tuple[bool, List[str]]:
        """Scan git diff for secrets and credentials.

        Returns:
            Tuple of (passed: bool, issues: list of found secrets)
        """
        try:
            diff_content = get_diff_content()
            if not diff_content:
                return True, []

            issues = []
            for secret_type, pattern in self.SECRET_PATTERNS.items():
                matches = re.finditer(pattern, diff_content, re.MULTILINE)
                for match in matches:
                    # Only flag additions (lines starting with +)
                    # Get the line containing the match
                    start_pos = diff_content.rfind('\n', 0, match.start()) + 1
                    end_pos = diff_content.find('\n', match.start())
                    if end_pos == -1:
                        end_pos = len(diff_content)
                    line = diff_content[start_pos:end_pos]
                    
                    if line.startswith('+') and not line.startswith('+++'):
                        issues.append(f"Potential {secret_type.replace('_', ' ')} detected in diff")

            if issues:
                return False, issues
            return True, []
        except Exception as e:
            return False, [f"Error scanning for secrets: {str(e)}"]

    def check_file_types(self) -> Tuple[bool, List[str]]:
        """Validate file types in git diff to block unwanted files.
        
        Blocks:
        - Binary files (by extension and content)
        - Files not in allowed extensions list
        
        Returns:
            Tuple of (passed: bool, issues: list of file type violations)
        """
        try:
            # Get list of files in diff
            success, output, _ = run_shell("git diff --cached --name-only --diff-filter=ACM", ignore_error=True)
            if not success:
                # Try without --cached (for unstaged changes)
                success, output, _ = run_shell("git diff --name-only --diff-filter=ACM", ignore_error=True)
            
            if not success or not output.strip():
                return True, []  # No files to check
            
            files = output.strip().split('\n')
            issues = []
            
            for file_path in files:
                if not file_path:
                    continue
                
                # Get file extension
                ext = self._get_extension(file_path)
                
                # Check if blocked extension
                if ext in self.blocked_extensions:
                    issues.append(f"Blocked file type: {file_path} ({ext} files not allowed)")
                    continue
                
                # Check if not in allowed extensions
                if ext and ext not in self.allowed_extensions:
                    issues.append(f"Disallowed file type: {file_path} ({ext} not in allowed list)")
                
                # Check for binary content
                if self._is_binary_content(file_path):
                    issues.append(f"Binary content detected: {file_path}")
            
            if issues:
                return False, issues
            return True, []
        except Exception as e:
            return False, [f"Error validating file types: {str(e)}"]
    
    def _get_extension(self, file_path: str) -> str:
        """Extract file extension from path.
        
        Args:
            file_path: Path to file
            
        Returns:
            File extension including dot (e.g., '.py') or empty string
        """
        if '.' not in file_path:
            return ''
        parts = file_path.rsplit('.', 1)
        if len(parts) == 2:
            return f".{parts[1]}"
        return ''
    
    def _is_binary_content(self, file_path: str) -> bool:
        """Check if file contains binary content.
        
        Uses null byte detection as indicator of binary content.
        
        Args:
            file_path: Path to file to check
            
        Returns:
            True if file appears to be binary
        """
        try:
            # Check if file exists in working directory
            success, _, _ = run_shell(f"test -f {shlex.quote(file_path)}", ignore_error=True)
            if not success:
                return False  # File doesn't exist (maybe deleted), skip check
            
            # Read first 8KB to check for null bytes
            success, output, _ = run_shell(
                f"head -c 8192 {shlex.quote(file_path)} | grep -q '\\x00' && echo 'binary' || echo 'text'",
                ignore_error=True
            )
            
            return output.strip() == 'binary'
        except Exception:
            # If we can't determine, err on the side of caution
            return False

    # Future guard hooks:
    # def validate_commit_message(self, msg): ...  # Message format
    # def request_human_approval(self): ...  # Human gate

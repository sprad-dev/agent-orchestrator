"""Validator factory for language-specific layer selection.

Selects appropriate syntax, test, and coverage validators based on
detected or configured project language.
"""

from typing import List, Optional
from src.verification.layer import Layer
from src.verification.language_detector import Language, detect_language
from src.verification.file_exists import FileExistsLayer
from src.verification.test_count import TestCountLayer
from src.verification.integration_check import IntegrationCheckLayer

# Python validators
from src.verification.syntax_check import SyntaxCheckLayer
from src.verification.pytest_validator import PytestValidatorLayer
from src.verification.coverage_check import CoverageCheckLayer

# Node.js/TypeScript validators
from src.verification.validators.nodejs_syntax import NodeJSSyntaxLayer
from src.verification.validators.nodejs_test import NodeJSTestValidatorLayer
from src.verification.validators.nodejs_coverage import NodeJSCoverageLayer

# .NET/C# validators
from src.verification.validators.dotnet_syntax import DotNetSyntaxLayer
from src.verification.validators.dotnet_test import DotNetTestValidatorLayer
from src.verification.validators.dotnet_coverage import DotNetCoverageLayer


class ValidatorFactory:
    """Factory for creating language-specific validators."""

    def __init__(self, language: Optional[Language] = None, project_path: str = "."):
        """Initialize validator factory.

        Args:
            language: Optional language override (if None, auto-detect)
            project_path: Path to project root for auto-detection
        """
        self.language = language or detect_language(project_path)

    def create_syntax_validator(self) -> Optional[Layer]:
        """Create syntax validator for detected language.

        Returns:
            Syntax validator layer, or None if not supported
        """
        if self.language == Language.PYTHON:
            return SyntaxCheckLayer()
        elif self.language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
            return NodeJSSyntaxLayer(use_typescript=(self.language == Language.TYPESCRIPT))
        elif self.language == Language.UNKNOWN:
            # Try to detect from files at runtime
            # For now, default to Python
            return SyntaxCheckLayer()

        return None

    def create_test_validator(self, test_command: str = None) -> Optional[Layer]:
        """Create test validator for detected language.

        Args:
            test_command: Optional test command override

        Returns:
            Test validator layer, or None if not supported
        """
        if self.language == Language.PYTHON:
            return PytestValidatorLayer()
        elif self.language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
            cmd = test_command or "npm test"
            return NodeJSTestValidatorLayer(test_command=cmd)
        elif self.language == Language.UNKNOWN:
            # Default to Python
            return PytestValidatorLayer()

        return None

    def create_coverage_validator(
        self, min_coverage: float = 80.0, test_command: str = None
    ) -> Optional[Layer]:
        """Create coverage validator for detected language.

        Args:
            min_coverage: Minimum coverage percentage
            test_command: Optional test command override

        Returns:
            Coverage validator layer, or None if not supported
        """
        if self.language == Language.PYTHON:
            cmd = test_command or "pytest"
            return CoverageCheckLayer(min_coverage=min_coverage, test_command=cmd)
        elif self.language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
            cmd = test_command or "npm test"
            return NodeJSCoverageLayer(min_coverage=min_coverage, test_command=cmd)
        elif self.language == Language.UNKNOWN:
            # Default to Python
            return CoverageCheckLayer(min_coverage=min_coverage, test_command=test_command or "pytest")

        return None

    def create_all_validators(
        self,
        enable_file_exists: bool = True,
        enable_syntax_check: bool = True,
        enable_test_count: bool = True,
        enable_test_validator: bool = True,
        enable_coverage: bool = True,
        enable_integration_check: bool = True,
        baseline_path: str = '.test_baseline',
        min_coverage: float = 80.0,
        test_command: str = None,
        integration_strict_mode: bool = False
    ) -> List[Layer]:
        """Create all validators for detected language.

        Args:
            enable_file_exists: Whether to enable file existence check
            enable_syntax_check: Whether to enable syntax check
            enable_test_count: Whether to enable test count check
            enable_test_validator: Whether to enable test validator
            enable_coverage: Whether to enable coverage check
            enable_integration_check: Whether to enable integration verification
            baseline_path: Path to test baseline file
            min_coverage: Minimum coverage percentage
            test_command: Command to run tests
            integration_strict_mode: If True, validate entrypoints exist in code

        Returns:
            List of validator layers
        """
        validators = []

        # Language-agnostic validators
        if enable_file_exists:
            validators.append(FileExistsLayer())

        # Language-specific validators
        if enable_syntax_check:
            syntax_validator = self.create_syntax_validator()
            if syntax_validator:
                validators.append(syntax_validator)

        if enable_test_count:
            validators.append(TestCountLayer(baseline_path))

        if enable_test_validator:
            test_validator = self.create_test_validator(test_command)
            if test_validator:
                validators.append(test_validator)

        if enable_coverage:
            coverage_validator = self.create_coverage_validator(min_coverage, test_command)
            if coverage_validator:
                validators.append(coverage_validator)

        if enable_integration_check:
            validators.append(IntegrationCheckLayer(strict_mode=integration_strict_mode))

        return validators

    def get_default_test_command(self) -> str:
        """Get default test command for detected language.

        Returns:
            Default test command string
        """
        if self.language == Language.PYTHON:
            return "pytest"
        elif self.language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
            return "npm test"
        else:
            return "pytest"  # Fallback

"""Tests for validator factory."""

import pytest
from src.verification.validator_factory import ValidatorFactory
from src.verification.language_detector import Language
from src.verification.syntax_check import SyntaxCheckLayer
from src.verification.pytest_validator import PytestValidatorLayer
from src.verification.coverage_check import CoverageCheckLayer
from src.verification.validators.nodejs_syntax import NodeJSSyntaxLayer
from src.verification.validators.nodejs_test import NodeJSTestValidatorLayer
from src.verification.validators.nodejs_coverage import NodeJSCoverageLayer
from src.verification.file_exists import FileExistsLayer
from src.verification.test_count import CountBaselineLayer
from src.verification.integration_check import IntegrationCheckLayer


class TestValidatorFactoryPython:
    """Test validator factory for Python projects."""

    def test_create_python_syntax_validator(self):
        """Create Python syntax validator."""
        factory = ValidatorFactory(language=Language.PYTHON)
        validator = factory.create_syntax_validator()
        assert isinstance(validator, SyntaxCheckLayer)

    def test_create_python_test_validator(self):
        """Create Python test validator."""
        factory = ValidatorFactory(language=Language.PYTHON)
        validator = factory.create_test_validator()
        assert isinstance(validator, PytestValidatorLayer)

    def test_create_python_coverage_validator(self):
        """Create Python coverage validator."""
        factory = ValidatorFactory(language=Language.PYTHON)
        validator = factory.create_coverage_validator(min_coverage=75.0)
        assert isinstance(validator, CoverageCheckLayer)
        assert validator.min_coverage == 75.0

    def test_get_python_default_test_command(self):
        """Get Python default test command."""
        factory = ValidatorFactory(language=Language.PYTHON)
        assert factory.get_default_test_command() == "pytest"


class TestValidatorFactoryJavaScript:
    """Test validator factory for JavaScript projects."""

    def test_create_javascript_syntax_validator(self):
        """Create JavaScript syntax validator."""
        factory = ValidatorFactory(language=Language.JAVASCRIPT)
        validator = factory.create_syntax_validator()
        assert isinstance(validator, NodeJSSyntaxLayer)
        assert validator.use_typescript is False

    def test_create_javascript_test_validator(self):
        """Create JavaScript test validator."""
        factory = ValidatorFactory(language=Language.JAVASCRIPT)
        validator = factory.create_test_validator()
        assert isinstance(validator, NodeJSTestValidatorLayer)
        assert validator.test_command == "npm test"

    def test_create_javascript_coverage_validator(self):
        """Create JavaScript coverage validator."""
        factory = ValidatorFactory(language=Language.JAVASCRIPT)
        validator = factory.create_coverage_validator(min_coverage=80.0)
        assert isinstance(validator, NodeJSCoverageLayer)
        assert validator.min_coverage == 80.0

    def test_get_javascript_default_test_command(self):
        """Get JavaScript default test command."""
        factory = ValidatorFactory(language=Language.JAVASCRIPT)
        assert factory.get_default_test_command() == "npm test"


class TestValidatorFactoryTypeScript:
    """Test validator factory for TypeScript projects."""

    def test_create_typescript_syntax_validator(self):
        """Create TypeScript syntax validator."""
        factory = ValidatorFactory(language=Language.TYPESCRIPT)
        validator = factory.create_syntax_validator()
        assert isinstance(validator, NodeJSSyntaxLayer)
        assert validator.use_typescript is True

    def test_create_typescript_test_validator(self):
        """Create TypeScript test validator."""
        factory = ValidatorFactory(language=Language.TYPESCRIPT)
        validator = factory.create_test_validator(test_command="jest")
        assert isinstance(validator, NodeJSTestValidatorLayer)
        assert validator.test_command == "jest"

    def test_create_typescript_coverage_validator(self):
        """Create TypeScript coverage validator."""
        factory = ValidatorFactory(language=Language.TYPESCRIPT)
        validator = factory.create_coverage_validator(min_coverage=90.0, test_command="jest")
        assert isinstance(validator, NodeJSCoverageLayer)
        assert validator.min_coverage == 90.0
        assert validator.test_command == "jest"


class TestValidatorFactoryUnknown:
    """Test validator factory for unknown language (fallback)."""

    def test_fallback_to_python_syntax(self):
        """Unknown language falls back to Python syntax validator."""
        factory = ValidatorFactory(language=Language.UNKNOWN)
        validator = factory.create_syntax_validator()
        assert isinstance(validator, SyntaxCheckLayer)

    def test_fallback_to_python_test(self):
        """Unknown language falls back to Python test validator."""
        factory = ValidatorFactory(language=Language.UNKNOWN)
        validator = factory.create_test_validator()
        assert isinstance(validator, PytestValidatorLayer)

    def test_fallback_to_python_coverage(self):
        """Unknown language falls back to Python coverage validator."""
        factory = ValidatorFactory(language=Language.UNKNOWN)
        validator = factory.create_coverage_validator()
        assert isinstance(validator, CoverageCheckLayer)


class TestValidatorFactoryCreateAll:
    """Test creating all validators at once."""

    def test_create_all_python_validators(self):
        """Create all validators for Python."""
        factory = ValidatorFactory(language=Language.PYTHON)
        validators = factory.create_all_validators(
            enable_file_exists=True,
            enable_syntax_check=True,
            enable_test_count=True,
            enable_test_validator=True,
            enable_coverage=True,
            enable_integration_check=True,
            min_coverage=85.0
        )

        # Should have 6 validators (all enabled)
        assert len(validators) == 6

        # Check types
        assert any(isinstance(v, FileExistsLayer) for v in validators)
        assert any(isinstance(v, SyntaxCheckLayer) for v in validators)
        assert any(isinstance(v, CountBaselineLayer) for v in validators)
        assert any(isinstance(v, PytestValidatorLayer) for v in validators)
        assert any(isinstance(v, CoverageCheckLayer) for v in validators)
        assert any(isinstance(v, IntegrationCheckLayer) for v in validators)

    def test_create_all_javascript_validators(self):
        """Create all validators for JavaScript."""
        factory = ValidatorFactory(language=Language.JAVASCRIPT)
        validators = factory.create_all_validators(
            enable_file_exists=True,
            enable_syntax_check=True,
            enable_test_count=True,
            enable_test_validator=True,
            enable_coverage=True,
            enable_integration_check=True
        )

        # Should have 6 validators (all enabled)
        assert len(validators) == 6

        # Check types
        assert any(isinstance(v, FileExistsLayer) for v in validators)
        assert any(isinstance(v, NodeJSSyntaxLayer) for v in validators)
        assert any(isinstance(v, CountBaselineLayer) for v in validators)
        assert any(isinstance(v, NodeJSTestValidatorLayer) for v in validators)
        assert any(isinstance(v, NodeJSCoverageLayer) for v in validators)
        assert any(isinstance(v, IntegrationCheckLayer) for v in validators)

    def test_create_all_with_selective_disable(self):
        """Create validators with some disabled."""
        factory = ValidatorFactory(language=Language.PYTHON)
        validators = factory.create_all_validators(
            enable_file_exists=True,
            enable_syntax_check=True,
            enable_test_count=False,
            enable_test_validator=False,
            enable_coverage=False,
            enable_integration_check=False
        )

        # Should have 2 validators (file exists + syntax)
        assert len(validators) == 2
        assert any(isinstance(v, FileExistsLayer) for v in validators)
        assert any(isinstance(v, SyntaxCheckLayer) for v in validators)

    def test_custom_test_command_propagates(self):
        """Custom test command propagates to validators."""
        factory = ValidatorFactory(language=Language.JAVASCRIPT)
        validators = factory.create_all_validators(
            enable_test_validator=True,
            enable_coverage=True,
            test_command="yarn test"
        )

        test_validator = next((v for v in validators if isinstance(v, NodeJSTestValidatorLayer)), None)
        coverage_validator = next((v for v in validators if isinstance(v, NodeJSCoverageLayer)), None)

        assert test_validator is not None
        assert test_validator.test_command == "yarn test"
        assert coverage_validator is not None
        assert coverage_validator.test_command == "yarn test"

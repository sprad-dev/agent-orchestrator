"""Layer coordinator for verification pipeline.

Orchestrates execution of verification layers in sequence.
Decouples layer management from runner logic.
"""

from typing import List, Dict, Tuple, Optional
from src.verification.layer import Layer, LayerResult
from src.verification.file_exists import FileExistsLayer
from src.verification.syntax_check import SyntaxCheckLayer
from src.verification.test_count import CountBaselineLayer
from src.verification.pytest_validator import PytestValidatorLayer
from src.verification.coverage_check import CoverageCheckLayer
from src.verification.integration_check import IntegrationCheckLayer
from src.verification.language_detector import Language
from src.verification.validator_factory import ValidatorFactory


class LayerCoordinator:
    """Coordinates execution of verification layers.
    
    Manages layer registration, execution, and result aggregation.
    Enables adding new layers without modifying runner.py.
    """
    
    def __init__(self):
        """Initialize coordinator with empty layer registry."""
        self.layers: Dict[int, List[Layer]] = {}
    
    def register_layer(self, layer: Layer) -> None:
        """Register a layer for execution.
        
        Args:
            layer: Layer instance to register
        """
        level = layer.level
        if level not in self.layers:
            self.layers[level] = []
        self.layers[level].append(layer)
    
    def register_default_layers(
        self,
        enable_file_exists: bool = True,
        enable_syntax_check: bool = True,
        enable_test_count: bool = True,
        enable_pytest_validator: bool = True,
        enable_coverage: bool = True,
        enable_integration_check: bool = True,
        baseline_path: str = '.test_baseline',
        min_coverage: float = 80.0,
        test_command: str = "pytest",
        integration_strict_mode: bool = False
    ) -> None:
        """Register all default verification layers.

        Args:
            enable_file_exists: Whether to enable file existence check
            enable_syntax_check: Whether to enable syntax check
            enable_test_count: Whether to enable test count check
            enable_pytest_validator: Whether to enable pytest validator
            enable_coverage: Whether to enable coverage check
            enable_integration_check: Whether to enable integration verification
            baseline_path: Path to test baseline file
            min_coverage: Minimum coverage percentage
            test_command: Command to run tests
            integration_strict_mode: If True, validate entrypoints exist in code
        """
        if enable_file_exists:
            self.register_layer(FileExistsLayer())

        if enable_syntax_check:
            self.register_layer(SyntaxCheckLayer())

        if enable_test_count:
            self.register_layer(CountBaselineLayer(baseline_path))

        if enable_pytest_validator:
            self.register_layer(PytestValidatorLayer())

        if enable_coverage:
            self.register_layer(CoverageCheckLayer(min_coverage, test_command))

        if enable_integration_check:
            self.register_layer(IntegrationCheckLayer(strict_mode=integration_strict_mode))

    def register_language_aware_layers(
        self,
        language: Optional[Language] = None,
        project_path: str = ".",
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
    ) -> None:
        """Register language-aware verification layers using validator factory.

        Args:
            language: Optional language override (if None, auto-detect)
            project_path: Path to project root for auto-detection
            enable_file_exists: Whether to enable file existence check
            enable_syntax_check: Whether to enable syntax check
            enable_test_count: Whether to enable test count check
            enable_test_validator: Whether to enable test validator
            enable_coverage: Whether to enable coverage check
            enable_integration_check: Whether to enable integration verification
            baseline_path: Path to test baseline file
            min_coverage: Minimum coverage percentage
            test_command: Command to run tests (if None, uses language default)
            integration_strict_mode: If True, validate entrypoints exist in code
        """
        factory = ValidatorFactory(language=language, project_path=project_path)

        # Use factory default test command if not provided
        if test_command is None:
            test_command = factory.get_default_test_command()

        # Register all validators from factory
        validators = factory.create_all_validators(
            enable_file_exists=enable_file_exists,
            enable_syntax_check=enable_syntax_check,
            enable_test_count=enable_test_count,
            enable_test_validator=enable_test_validator,
            enable_coverage=enable_coverage,
            enable_integration_check=enable_integration_check,
            baseline_path=baseline_path,
            min_coverage=min_coverage,
            test_command=test_command,
            integration_strict_mode=integration_strict_mode
        )

        for validator in validators:
            self.register_layer(validator)

    def run_layers(self, layer_level: int, **kwargs) -> Tuple[bool, List[LayerResult]]:
        """Execute all layers at a given level.
        
        Args:
            layer_level: Level number to execute (e.g., 1, 2, 3)
            **kwargs: Parameters to pass to layers
            
        Returns:
            Tuple of (all_passed, results)
            - all_passed: True if all layers at this level passed
            - results: List of LayerResult from each layer
        """
        if layer_level not in self.layers:
            return True, []
        
        results = []
        all_passed = True
        
        for layer in self.layers[layer_level]:
            if not layer.is_enabled():
                continue
            
            try:
                result = layer.run(**kwargs)
                results.append(result)
                
                if not result.passed:
                    all_passed = False
            except Exception as e:
                result = LayerResult(
                    passed=False,
                    message=f"{layer.name} failed with exception",
                    error_details=[str(e)]
                )
                results.append(result)
                all_passed = False
        
        return all_passed, results
    
    def get_layers(self, level: Optional[int] = None) -> List[Layer]:
        """Get registered layers, optionally filtered by level.
        
        Args:
            level: Optional level to filter by
            
        Returns:
            List of registered layers
        """
        if level is None:
            all_layers = []
            for level_layers in self.layers.values():
                all_layers.extend(level_layers)
            return all_layers
        
        return self.layers.get(level, [])
    
    def clear(self) -> None:
        """Clear all registered layers."""
        self.layers.clear()

    def execute_layer_level_with_output(
        self,
        level: int,
        level_name: str,
        output_lines: List[str],
        **kwargs
    ) -> Tuple[bool, Optional[str]]:
        """Execute layers at a level and format output.

        Args:
            level: Layer level to execute
            level_name: Display name for the level (e.g., "FILE EXISTENCE CHECK")
            output_lines: List to append success messages to
            **kwargs: Parameters to pass to layers

        Returns:
            Tuple of (passed, error_output)
            - passed: True if all layers passed
            - error_output: Formatted error message if failed, None otherwise
        """
        passed, results = self.run_layers(level, **kwargs)

        for result in results:
            if result.error_details:
                error = f"{level_name} FAILED:\n" + "\n".join(result.error_details)
                return False, error
            output_lines.append(f"✓ L{level} {result.message}")

        if not passed:
            return False, None

        return True, None

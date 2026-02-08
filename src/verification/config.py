"""Configuration management for verification thresholds.

Supports YAML and TOML configuration files for verification settings.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import tomli
    HAS_TOMLI = True
except ImportError:
    HAS_TOMLI = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class VerificationConfig:
    """Configuration for verification thresholds and settings."""
    
    # Layer enable/disable
    enable_file_exists_check: bool = True
    enable_syntax_check: bool = True
    enable_test_count_check: bool = True
    enable_pytest_validation: bool = True
    enable_coverage_check: bool = False
    enable_integration_check: bool = True
    integration_strict_mode: bool = False
    
    # Test configuration
    test_command: str = "pytest"
    test_timeout_seconds: int = 300
    baseline_path: str = ".test_baseline"
    
    # Coverage thresholds
    coverage_minimum_percent: float = 0.0
    coverage_branch_minimum_percent: float = 0.0
    
    # Test count requirements
    minimum_test_count: int = 0
    allow_test_deletion: bool = False
    
    # Performance baselines
    max_execution_time_seconds: Optional[float] = None
    performance_baseline_path: Optional[str] = None
    
    # Additional settings
    strict_mode: bool = False
    fail_fast: bool = False
    verbose: bool = False

    # Retry configuration for transient failures
    max_retries: int = 3
    retry_initial_delay: float = 1.0
    retry_backoff_multiplier: float = 2.0
    retry_max_delay: float = 60.0
    retry_jitter: bool = True

    # Custom settings (for extensibility)
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VerificationConfig':
        """Create config from dictionary with validation.
        
        Args:
            data: Configuration dictionary
            
        Returns:
            VerificationConfig instance
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Extract known fields
        known_fields = {
            'enable_file_exists_check',
            'enable_syntax_check',
            'enable_test_count_check',
            'enable_pytest_validation',
            'enable_coverage_check',
            'enable_integration_check',
            'integration_strict_mode',
            'test_command',
            'test_timeout_seconds',
            'baseline_path',
            'coverage_minimum_percent',
            'coverage_branch_minimum_percent',
            'minimum_test_count',
            'allow_test_deletion',
            'max_execution_time_seconds',
            'performance_baseline_path',
            'strict_mode',
            'fail_fast',
            'verbose',
            'max_retries',
            'retry_initial_delay',
            'retry_backoff_multiplier',
            'retry_max_delay',
            'retry_jitter',
        }
        
        config_kwargs = {}
        custom_settings = {}
        
        for key, value in data.items():
            if key in known_fields:
                config_kwargs[key] = value
            else:
                custom_settings[key] = value
        
        if custom_settings:
            config_kwargs['custom_settings'] = custom_settings
        
        config = cls(**config_kwargs)
        config.validate()
        return config
    
    def validate(self):
        """Validate configuration values.
        
        Raises:
            ValueError: If any configuration value is invalid
        """
        errors = []
        
        # Validate test timeout
        if self.test_timeout_seconds <= 0:
            errors.append(f"test_timeout_seconds must be positive, got {self.test_timeout_seconds}")
        
        # Validate coverage thresholds
        if not (0.0 <= self.coverage_minimum_percent <= 100.0):
            errors.append(f"coverage_minimum_percent must be between 0 and 100, got {self.coverage_minimum_percent}")
        
        if not (0.0 <= self.coverage_branch_minimum_percent <= 100.0):
            errors.append(f"coverage_branch_minimum_percent must be between 0 and 100, got {self.coverage_branch_minimum_percent}")
        
        # Validate minimum test count
        if self.minimum_test_count < 0:
            errors.append(f"minimum_test_count must be non-negative, got {self.minimum_test_count}")
        
        # Validate max execution time
        if self.max_execution_time_seconds is not None and self.max_execution_time_seconds <= 0:
            errors.append(f"max_execution_time_seconds must be positive, got {self.max_execution_time_seconds}")
        
        # Validate test command is not empty
        if not self.test_command or not self.test_command.strip():
            errors.append("test_command cannot be empty")

        # Validate retry configuration
        if self.max_retries < 0:
            errors.append(f"max_retries must be non-negative, got {self.max_retries}")

        if self.retry_initial_delay <= 0:
            errors.append(f"retry_initial_delay must be positive, got {self.retry_initial_delay}")

        if self.retry_backoff_multiplier < 1.0:
            errors.append(f"retry_backoff_multiplier must be >= 1.0, got {self.retry_backoff_multiplier}")

        if self.retry_max_delay <= 0:
            errors.append(f"retry_max_delay must be positive, got {self.retry_max_delay}")

        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary.
        
        Returns:
            Dictionary representation of config (excludes None values)
        """
        result = {
            'enable_file_exists_check': self.enable_file_exists_check,
            'enable_syntax_check': self.enable_syntax_check,
            'enable_test_count_check': self.enable_test_count_check,
            'enable_pytest_validation': self.enable_pytest_validation,
            'enable_coverage_check': self.enable_coverage_check,
            'enable_integration_check': self.enable_integration_check,
            'integration_strict_mode': self.integration_strict_mode,
            'test_command': self.test_command,
            'test_timeout_seconds': self.test_timeout_seconds,
            'baseline_path': self.baseline_path,
            'coverage_minimum_percent': self.coverage_minimum_percent,
            'coverage_branch_minimum_percent': self.coverage_branch_minimum_percent,
            'minimum_test_count': self.minimum_test_count,
            'allow_test_deletion': self.allow_test_deletion,
            'strict_mode': self.strict_mode,
            'fail_fast': self.fail_fast,
            'verbose': self.verbose,
            'max_retries': self.max_retries,
            'retry_initial_delay': self.retry_initial_delay,
            'retry_backoff_multiplier': self.retry_backoff_multiplier,
            'retry_max_delay': self.retry_max_delay,
            'retry_jitter': self.retry_jitter,
        }
        
        # Add optional fields only if not None (for TOML compatibility)
        if self.max_execution_time_seconds is not None:
            result['max_execution_time_seconds'] = self.max_execution_time_seconds
        if self.performance_baseline_path is not None:
            result['performance_baseline_path'] = self.performance_baseline_path
        
        # Add custom settings
        result.update(self.custom_settings)
        
        return result


def load_config(config_path: Optional[str] = None) -> VerificationConfig:
    """Load verification configuration from file.
    
    Searches for config files in the following order:
    1. Explicit path provided
    2. .verification.toml
    3. .verification.yaml / .verification.yml
    4. verification.toml
    5. verification.yaml / verification.yml
    
    If no config file is found, returns default configuration.
    
    Args:
        config_path: Optional explicit path to config file
        
    Returns:
        VerificationConfig instance
        
    Raises:
        ValueError: If config file is invalid
        FileNotFoundError: If explicit config_path is provided but not found
    """
    # If explicit path provided, use it
    if config_path:
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        return _load_config_file(config_file)
    
    # Search for config files
    search_paths = [
        '.verification.toml',
        '.verification.yaml',
        '.verification.yml',
        'verification.toml',
        'verification.yaml',
        'verification.yml',
    ]
    
    for path_str in search_paths:
        config_file = Path(path_str)
        if config_file.exists():
            return _load_config_file(config_file)
    
    # No config file found, return defaults
    return VerificationConfig()


def _load_config_file(config_path: Path) -> VerificationConfig:
    """Load config from a specific file.
    
    Args:
        config_path: Path to config file
        
    Returns:
        VerificationConfig instance
        
    Raises:
        ValueError: If config format is unsupported or invalid
    """
    suffix = config_path.suffix.lower()
    
    if suffix == '.toml':
        return _load_toml_config(config_path)
    elif suffix in ['.yaml', '.yml']:
        return _load_yaml_config(config_path)
    else:
        raise ValueError(f"Unsupported config format: {suffix} (supported: .toml, .yaml, .yml)")


def _load_toml_config(config_path: Path) -> VerificationConfig:
    """Load TOML configuration file.
    
    Args:
        config_path: Path to TOML file
        
    Returns:
        VerificationConfig instance
        
    Raises:
        ValueError: If TOML is invalid or tomli not installed
    """
    if not HAS_TOMLI:
        raise ValueError("tomli package required for TOML support. Install with: pip install tomli")
    
    try:
        with open(config_path, 'rb') as f:
            data = tomli.load(f)
    except tomli.TOMLDecodeError as e:
        raise ValueError(f"Invalid TOML in {config_path}: {e}")
    except IOError as e:
        raise ValueError(f"Failed to read {config_path}: {e}")
    
    # Support both flat structure and [verification] section
    if 'verification' in data:
        config_data = data['verification']
    else:
        config_data = data
    
    return VerificationConfig.from_dict(config_data)


def _load_yaml_config(config_path: Path) -> VerificationConfig:
    """Load YAML configuration file.
    
    Args:
        config_path: Path to YAML file
        
    Returns:
        VerificationConfig instance
        
    Raises:
        ValueError: If YAML is invalid or PyYAML not installed
    """
    if not HAS_YAML:
        raise ValueError("PyYAML package required for YAML support. Install with: pip install pyyaml")
    
    try:
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}")
    except IOError as e:
        raise ValueError(f"Failed to read {config_path}: {e}")
    
    if data is None:
        data = {}
    
    # Support both flat structure and verification: key
    if 'verification' in data:
        config_data = data['verification']
    else:
        config_data = data
    
    return VerificationConfig.from_dict(config_data)


def save_config(config: VerificationConfig, config_path: str, format: str = 'toml'):
    """Save configuration to file.
    
    Args:
        config: Configuration to save
        config_path: Path to save config file
        format: Format to save ('toml' or 'yaml')
        
    Raises:
        ValueError: If format is unsupported or required package not installed
    """
    config.validate()
    
    if format == 'toml':
        _save_toml_config(config, Path(config_path))
    elif format == 'yaml':
        _save_yaml_config(config, Path(config_path))
    else:
        raise ValueError(f"Unsupported format: {format} (supported: toml, yaml)")


def _save_toml_config(config: VerificationConfig, config_path: Path):
    """Save config as TOML.
    
    Args:
        config: Configuration to save
        config_path: Path to save file
        
    Raises:
        ValueError: If tomli_w not installed
    """
    try:
        import tomli_w
    except ImportError:
        raise ValueError("tomli_w package required for TOML writing. Install with: pip install tomli-w")
    
    data = {'verification': config.to_dict()}
    
    with open(config_path, 'wb') as f:
        tomli_w.dump(data, f)


def _save_yaml_config(config: VerificationConfig, config_path: Path):
    """Save config as YAML.
    
    Args:
        config: Configuration to save
        config_path: Path to save file
        
    Raises:
        ValueError: If PyYAML not installed
    """
    if not HAS_YAML:
        raise ValueError("PyYAML package required for YAML support. Install with: pip install pyyaml")
    
    data = {'verification': config.to_dict()}
    
    with open(config_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

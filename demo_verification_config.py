#!/usr/bin/env python3
"""Demo script showing configuration management features."""

import tempfile
import os
from pathlib import Path
from src.verification.config import (
    VerificationConfig,
    load_config,
    save_config,
)
from src.verification.runner import VerificationRunner


def demo_basic_config():
    """Demonstrate basic configuration."""
    print("=" * 60)
    print("DEMO: Basic Configuration")
    print("=" * 60)
    
    config = VerificationConfig(
        enable_syntax_check=True,
        test_command="pytest -v",
        coverage_minimum_percent=80.0,
        minimum_test_count=5,
    )
    
    print(f"Test command: {config.test_command}")
    print(f"Coverage minimum: {config.coverage_minimum_percent}%")
    print(f"Minimum test count: {config.minimum_test_count}")
    print(f"Syntax check enabled: {config.enable_syntax_check}")
    print()


def demo_config_validation():
    """Demonstrate configuration validation."""
    print("=" * 60)
    print("DEMO: Configuration Validation")
    print("=" * 60)
    
    # Valid config
    valid_config = VerificationConfig(coverage_minimum_percent=75.0)
    try:
        valid_config.validate()
        print("✓ Valid config passed validation")
    except ValueError as e:
        print(f"✗ Validation failed: {e}")
    
    # Invalid config
    invalid_config = VerificationConfig(coverage_minimum_percent=150.0)
    try:
        invalid_config.validate()
        print("✗ Invalid config should have failed")
    except ValueError as e:
        print(f"✓ Invalid config correctly rejected: {str(e)[:50]}...")
    print()


def demo_toml_config():
    """Demonstrate TOML configuration file."""
    print("=" * 60)
    print("DEMO: TOML Configuration File")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / ".verification.toml"
        
        # Create config
        config = VerificationConfig(
            enable_syntax_check=False,
            test_command="pytest -x --tb=short",
            coverage_minimum_percent=85.0,
            strict_mode=True,
        )
        
        # Save as TOML
        save_config(config, str(config_file), format='toml')
        print(f"✓ Saved config to {config_file.name}")
        
        # Load it back
        loaded = load_config(str(config_file))
        print(f"✓ Loaded config from {config_file.name}")
        print(f"  - Test command: {loaded.test_command}")
        print(f"  - Coverage: {loaded.coverage_minimum_percent}%")
        print(f"  - Strict mode: {loaded.strict_mode}")
        print()


def demo_yaml_config():
    """Demonstrate YAML configuration file."""
    print("=" * 60)
    print("DEMO: YAML Configuration File")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "verification.yaml"
        
        # Create config
        config = VerificationConfig(
            test_command="pytest --cov",
            coverage_minimum_percent=90.0,
            minimum_test_count=20,
        )
        
        # Save as YAML
        save_config(config, str(config_file), format='yaml')
        print(f"✓ Saved config to {config_file.name}")
        
        # Load it back
        loaded = load_config(str(config_file))
        print(f"✓ Loaded config from {config_file.name}")
        print(f"  - Test command: {loaded.test_command}")
        print(f"  - Coverage: {loaded.coverage_minimum_percent}%")
        print(f"  - Min tests: {loaded.minimum_test_count}")
        print()


def demo_runner_integration():
    """Demonstrate integration with VerificationRunner."""
    print("=" * 60)
    print("DEMO: Runner Integration")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.toml"
        config_file.write_text("""
[verification]
enable_syntax_check = false
test_command = "pytest -v"
baseline_path = ".custom_baseline"
coverage_minimum_percent = 85.0
""")
        
        # Create runner with config file
        runner = VerificationRunner(config_path=str(config_file))
        
        print(f"✓ Runner created with config file")
        print(f"  - Test command: {runner.verify_cmd}")
        print(f"  - Baseline path: {runner.baseline_path}")
        print(f"  - Syntax check: {runner.enable_syntax_check}")
        print(f"  - Coverage min: {runner.config.coverage_minimum_percent}%")
        print()


def demo_custom_settings():
    """Demonstrate custom settings support."""
    print("=" * 60)
    print("DEMO: Custom Settings (Extensibility)")
    print("=" * 60)
    
    config = VerificationConfig.from_dict({
        'test_command': 'pytest',
        'coverage_minimum_percent': 80.0,
        'project_name': 'my-project',
        'ci_mode': True,
        'custom_threshold': 42,
    })
    
    print(f"✓ Created config with custom settings")
    print(f"  - Standard: test_command = {config.test_command}")
    print(f"  - Standard: coverage = {config.coverage_minimum_percent}%")
    print(f"  - Custom: project_name = {config.custom_settings.get('project_name')}")
    print(f"  - Custom: ci_mode = {config.custom_settings.get('ci_mode')}")
    print(f"  - Custom: custom_threshold = {config.custom_settings.get('custom_threshold')}")
    print()


def main():
    """Run all demos."""
    print("\n")
    print("=" * 60)
    print("VERIFICATION CONFIGURATION MANAGEMENT")
    print("Feature Demonstration")
    print("=" * 60)
    print()
    
    demo_basic_config()
    demo_config_validation()
    demo_toml_config()
    demo_yaml_config()
    demo_runner_integration()
    demo_custom_settings()
    
    print("=" * 60)
    print("✅ All demos completed successfully!")
    print("=" * 60)
    print()
    print("For more information, see:")
    print("  - docs/VERIFICATION_CONFIG.md")
    print("  - docs/verification.example.toml")
    print("  - docs/verification.example.yaml")
    print()


if __name__ == "__main__":
    main()

"""Tests for verification configuration management."""

import pytest
import tempfile
import os
from pathlib import Path
from src.verification.config import (
    VerificationConfig,
    load_config,
    save_config,
    _load_toml_config,
    _load_yaml_config,
)


class TestVerificationConfig:
    """Tests for VerificationConfig class."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = VerificationConfig()
        
        assert config.enable_syntax_check is True
        assert config.enable_test_count_check is True
        assert config.enable_pytest_validation is True
        assert config.enable_coverage_check is False
        assert config.test_command == "pytest"
        assert config.test_timeout_seconds == 300
        assert config.baseline_path == ".test_baseline"
        assert config.coverage_minimum_percent == 0.0
        assert config.minimum_test_count == 0
        assert config.allow_test_deletion is False
        assert config.strict_mode is False
    
    def test_custom_values(self):
        """Test creating config with custom values."""
        config = VerificationConfig(
            enable_syntax_check=False,
            test_command="pytest -v",
            test_timeout_seconds=600,
            coverage_minimum_percent=80.0,
            minimum_test_count=5,
            strict_mode=True,
        )
        
        assert config.enable_syntax_check is False
        assert config.test_command == "pytest -v"
        assert config.test_timeout_seconds == 600
        assert config.coverage_minimum_percent == 80.0
        assert config.minimum_test_count == 5
        assert config.strict_mode is True
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            'enable_syntax_check': False,
            'test_command': 'pytest -v',
            'coverage_minimum_percent': 75.5,
            'minimum_test_count': 10,
            'custom_field': 'custom_value',
        }
        
        config = VerificationConfig.from_dict(data)
        
        assert config.enable_syntax_check is False
        assert config.test_command == 'pytest -v'
        assert config.coverage_minimum_percent == 75.5
        assert config.minimum_test_count == 10
        assert config.custom_settings['custom_field'] == 'custom_value'
    
    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = VerificationConfig(
            test_command="pytest -v",
            coverage_minimum_percent=80.0,
        )
        config.custom_settings['custom_key'] = 'custom_value'
        
        data = config.to_dict()
        
        assert data['test_command'] == 'pytest -v'
        assert data['coverage_minimum_percent'] == 80.0
        assert data['custom_key'] == 'custom_value'
    
    def test_validate_success(self):
        """Test validation passes for valid config."""
        config = VerificationConfig(
            test_timeout_seconds=100,
            coverage_minimum_percent=50.0,
            coverage_branch_minimum_percent=40.0,
            minimum_test_count=5,
            max_execution_time_seconds=120.0,
        )
        
        # Should not raise
        config.validate()
    
    def test_validate_negative_timeout(self):
        """Test validation fails for negative timeout."""
        config = VerificationConfig(test_timeout_seconds=-10)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert 'test_timeout_seconds must be positive' in str(exc_info.value)
    
    def test_validate_invalid_coverage_percent(self):
        """Test validation fails for invalid coverage percentage."""
        config = VerificationConfig(coverage_minimum_percent=150.0)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert 'coverage_minimum_percent must be between 0 and 100' in str(exc_info.value)
    
    def test_validate_negative_coverage_percent(self):
        """Test validation fails for negative coverage percentage."""
        config = VerificationConfig(coverage_minimum_percent=-10.0)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert 'coverage_minimum_percent must be between 0 and 100' in str(exc_info.value)
    
    def test_validate_invalid_branch_coverage(self):
        """Test validation fails for invalid branch coverage."""
        config = VerificationConfig(coverage_branch_minimum_percent=101.0)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert 'coverage_branch_minimum_percent must be between 0 and 100' in str(exc_info.value)
    
    def test_validate_negative_test_count(self):
        """Test validation fails for negative test count."""
        config = VerificationConfig(minimum_test_count=-5)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert 'minimum_test_count must be non-negative' in str(exc_info.value)
    
    def test_validate_invalid_max_execution_time(self):
        """Test validation fails for invalid max execution time."""
        config = VerificationConfig(max_execution_time_seconds=-1.0)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert 'max_execution_time_seconds must be positive' in str(exc_info.value)
    
    def test_validate_empty_test_command(self):
        """Test validation fails for empty test command."""
        config = VerificationConfig(test_command="")
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert 'test_command cannot be empty' in str(exc_info.value)
    
    def test_validate_whitespace_test_command(self):
        """Test validation fails for whitespace-only test command."""
        config = VerificationConfig(test_command="   ")
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert 'test_command cannot be empty' in str(exc_info.value)
    
    def test_validate_multiple_errors(self):
        """Test validation reports multiple errors."""
        config = VerificationConfig(
            test_timeout_seconds=-10,
            coverage_minimum_percent=150.0,
            minimum_test_count=-5,
        )
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        error_msg = str(exc_info.value)
        assert 'test_timeout_seconds' in error_msg
        assert 'coverage_minimum_percent' in error_msg
        assert 'minimum_test_count' in error_msg


class TestLoadConfig:
    """Tests for loading configuration from files."""
    
    def test_load_default_when_no_file(self):
        """Test returns default config when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = load_config()
                
                assert config.test_command == "pytest"
                assert config.enable_syntax_check is True
            finally:
                os.chdir(original_cwd)
    
    def test_load_explicit_file_not_found(self):
        """Test raises error when explicit path not found."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.toml")
    
    def test_load_toml_flat_structure(self):
        """Test loading TOML with flat structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / ".verification.toml"
            config_file.write_text("""
enable_syntax_check = false
test_command = "pytest -v"
coverage_minimum_percent = 80.0
minimum_test_count = 5
""")
            
            config = load_config(str(config_file))
            
            assert config.enable_syntax_check is False
            assert config.test_command == "pytest -v"
            assert config.coverage_minimum_percent == 80.0
            assert config.minimum_test_count == 5
    
    def test_load_toml_with_section(self):
        """Test loading TOML with [verification] section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            config_file.write_text("""
[verification]
enable_syntax_check = false
test_command = "pytest -v"
coverage_minimum_percent = 85.5
""")
            
            config = load_config(str(config_file))
            
            assert config.enable_syntax_check is False
            assert config.test_command == "pytest -v"
            assert config.coverage_minimum_percent == 85.5
    
    def test_load_yaml_flat_structure(self):
        """Test loading YAML with flat structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / ".verification.yaml"
            config_file.write_text("""
enable_syntax_check: false
test_command: pytest -v
coverage_minimum_percent: 90.0
minimum_test_count: 10
""")
            
            config = load_config(str(config_file))
            
            assert config.enable_syntax_check is False
            assert config.test_command == "pytest -v"
            assert config.coverage_minimum_percent == 90.0
            assert config.minimum_test_count == 10
    
    def test_load_yaml_with_section(self):
        """Test loading YAML with verification section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "verification.yml"
            config_file.write_text("""
verification:
  enable_syntax_check: false
  test_command: pytest -v
  coverage_minimum_percent: 95.0
""")
            
            config = load_config(str(config_file))
            
            assert config.enable_syntax_check is False
            assert config.test_command == "pytest -v"
            assert config.coverage_minimum_percent == 95.0
    
    def test_load_yaml_empty_file(self):
        """Test loading empty YAML file returns defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text("")
            
            config = load_config(str(config_file))
            
            assert config.test_command == "pytest"
            assert config.enable_syntax_check is True
    
    def test_load_invalid_toml(self):
        """Test error on invalid TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            config_file.write_text("invalid toml [[[")
            
            with pytest.raises(ValueError) as exc_info:
                load_config(str(config_file))
            
            assert 'Invalid TOML' in str(exc_info.value)
    
    def test_load_invalid_yaml(self):
        """Test error on invalid YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text("invalid: yaml: [[[: ")
            
            with pytest.raises(ValueError) as exc_info:
                load_config(str(config_file))
            
            assert 'Invalid YAML' in str(exc_info.value)
    
    def test_load_unsupported_format(self):
        """Test error on unsupported file format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text('{"test": "value"}')
            
            with pytest.raises(ValueError) as exc_info:
                load_config(str(config_file))
            
            assert 'Unsupported config format' in str(exc_info.value)
    
    def test_load_with_validation_errors(self):
        """Test that validation errors are raised during load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            config_file.write_text("""
test_timeout_seconds = -100
coverage_minimum_percent = 200.0
""")
            
            with pytest.raises(ValueError) as exc_info:
                load_config(str(config_file))
            
            error_msg = str(exc_info.value)
            assert 'validation failed' in error_msg.lower()
    
    def test_search_order(self):
        """Test config file search order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Create multiple config files
                Path(".verification.toml").write_text('test_timeout_seconds = 100')
                Path("verification.yaml").write_text('test_timeout_seconds: 200')
                
                config = load_config()
                
                # Should load .verification.toml first
                assert config.test_timeout_seconds == 100
            finally:
                os.chdir(original_cwd)


class TestSaveConfig:
    """Tests for saving configuration to files."""
    
    def test_save_toml(self):
        """Test saving config as TOML."""
        config = VerificationConfig(
            enable_syntax_check=False,
            test_command="pytest -v",
            coverage_minimum_percent=80.0,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            
            try:
                save_config(config, str(config_file), format='toml')
                
                # Load it back
                loaded = load_config(str(config_file))
                
                assert loaded.enable_syntax_check is False
                assert loaded.test_command == "pytest -v"
                assert loaded.coverage_minimum_percent == 80.0
            except ValueError as e:
                if 'tomli_w' in str(e):
                    pytest.skip("tomli_w not installed")
                raise
    
    def test_save_yaml(self):
        """Test saving config as YAML."""
        config = VerificationConfig(
            enable_syntax_check=False,
            test_command="pytest -v",
            coverage_minimum_percent=85.0,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            
            try:
                save_config(config, str(config_file), format='yaml')
                
                # Load it back
                loaded = load_config(str(config_file))
                
                assert loaded.enable_syntax_check is False
                assert loaded.test_command == "pytest -v"
                assert loaded.coverage_minimum_percent == 85.0
            except ValueError as e:
                if 'PyYAML' in str(e):
                    pytest.skip("PyYAML not installed")
                raise
    
    def test_save_unsupported_format(self):
        """Test error on unsupported save format."""
        config = VerificationConfig()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            
            with pytest.raises(ValueError) as exc_info:
                save_config(config, str(config_file), format='json')
            
            assert 'Unsupported format' in str(exc_info.value)
    
    def test_save_validates_config(self):
        """Test that save validates config before writing."""
        config = VerificationConfig(test_timeout_seconds=-100)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            
            with pytest.raises(ValueError) as exc_info:
                save_config(config, str(config_file), format='toml')
            
            assert 'validation failed' in str(exc_info.value).lower()


class TestIntegration:
    """Integration tests for config system."""
    
    def test_roundtrip_toml(self):
        """Test saving and loading TOML preserves values."""
        original = VerificationConfig(
            enable_syntax_check=False,
            enable_test_count_check=True,
            enable_pytest_validation=False,
            test_command="pytest -v -x",
            test_timeout_seconds=600,
            coverage_minimum_percent=75.5,
            coverage_branch_minimum_percent=60.0,
            minimum_test_count=10,
            allow_test_deletion=True,
            strict_mode=True,
            fail_fast=True,
            verbose=True,
        )
        original.custom_settings['custom_key'] = 'custom_value'
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            
            try:
                save_config(original, str(config_file), format='toml')
                loaded = load_config(str(config_file))
                
                assert loaded.enable_syntax_check == original.enable_syntax_check
                assert loaded.test_command == original.test_command
                assert loaded.test_timeout_seconds == original.test_timeout_seconds
                assert loaded.coverage_minimum_percent == original.coverage_minimum_percent
                assert loaded.coverage_branch_minimum_percent == original.coverage_branch_minimum_percent
                assert loaded.minimum_test_count == original.minimum_test_count
                assert loaded.allow_test_deletion == original.allow_test_deletion
                assert loaded.strict_mode == original.strict_mode
                assert loaded.custom_settings['custom_key'] == 'custom_value'
            except ValueError as e:
                if 'tomli' in str(e):
                    pytest.skip("tomli/tomli_w not installed")
                raise
    
    def test_roundtrip_yaml(self):
        """Test saving and loading YAML preserves values."""
        original = VerificationConfig(
            enable_syntax_check=True,
            test_command="pytest --cov",
            coverage_minimum_percent=90.0,
            minimum_test_count=20,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            
            try:
                save_config(original, str(config_file), format='yaml')
                loaded = load_config(str(config_file))
                
                assert loaded.enable_syntax_check == original.enable_syntax_check
                assert loaded.test_command == original.test_command
                assert loaded.coverage_minimum_percent == original.coverage_minimum_percent
                assert loaded.minimum_test_count == original.minimum_test_count
            except ValueError as e:
                if 'PyYAML' in str(e):
                    pytest.skip("PyYAML not installed")
                raise

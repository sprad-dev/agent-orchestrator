"""Integration tests for VerificationRunner with config."""

import pytest
import tempfile
from pathlib import Path
from src.verification.runner import VerificationRunner
from src.verification.config import VerificationConfig


def test_runner_uses_default_config():
    """Test runner uses default config when none provided."""
    runner = VerificationRunner()
    
    assert runner.verify_cmd == "pytest"
    assert runner.baseline_path == ".test_baseline"
    assert runner.enable_syntax_check is True
    assert runner.enable_test_count_check is True
    assert runner.enable_pytest_validation is True


def test_runner_with_explicit_config():
    """Test runner uses explicit config."""
    config = VerificationConfig(
        enable_syntax_check=False,
        test_command="pytest -v",
        baseline_path=".custom_baseline",
    )
    
    runner = VerificationRunner(config=config)
    
    assert runner.verify_cmd == "pytest -v"
    assert runner.baseline_path == ".custom_baseline"
    assert runner.enable_syntax_check is False


def test_runner_loads_config_from_file():
    """Test runner loads config from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.toml"
        config_file.write_text("""
[verification]
enable_syntax_check = false
test_command = "pytest -x"
baseline_path = ".my_baseline"
coverage_minimum_percent = 80.0
""")
        
        runner = VerificationRunner(config_path=str(config_file))
        
        assert runner.verify_cmd == "pytest -x"
        assert runner.baseline_path == ".my_baseline"
        assert runner.enable_syntax_check is False
        assert runner.config.coverage_minimum_percent == 80.0


def test_runner_backwards_compatible():
    """Test runner maintains backwards compatibility with old constructor."""
    runner = VerificationRunner(verify_cmd="pytest -v", baseline_path=".old_baseline")
    
    # Should use constructor args when config has defaults
    assert runner.verify_cmd == "pytest -v"
    assert runner.baseline_path == ".old_baseline"


def test_runner_config_overrides_constructor_args():
    """Test config values override constructor args."""
    config = VerificationConfig(
        test_command="pytest --cov",
        baseline_path=".config_baseline",
    )
    
    runner = VerificationRunner(
        verify_cmd="pytest",
        baseline_path=".test_baseline",
        config=config
    )
    
    # Config should override constructor args
    assert runner.verify_cmd == "pytest --cov"
    assert runner.baseline_path == ".config_baseline"


def test_runner_accesses_config_settings():
    """Test runner can access additional config settings."""
    config = VerificationConfig(
        coverage_minimum_percent=85.0,
        strict_mode=True,
        max_execution_time_seconds=120.0,
    )
    
    runner = VerificationRunner(config=config)
    
    assert runner.config.coverage_minimum_percent == 85.0
    assert runner.config.strict_mode is True
    assert runner.config.max_execution_time_seconds == 120.0

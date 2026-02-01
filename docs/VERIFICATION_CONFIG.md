# Verification Configuration Management

## Overview

The verification system supports project-specific configuration files to customize verification thresholds, enable/disable layers, and set operational parameters.

## Supported Formats

- **TOML**: `.verification.toml`, `verification.toml`
- **YAML**: `.verification.yaml`, `.verification.yml`, `verification.yaml`, `verification.yml`

## Configuration Search Order

The system searches for configuration files in the following order:
1. Explicit path provided via `config_path` parameter
2. `.verification.toml`
3. `.verification.yaml` / `.verification.yml`
4. `verification.toml`
5. `verification.yaml` / `verification.yml`

If no configuration file is found, default values are used.

## Configuration Options

### Layer Enable/Disable

Control which verification layers are active:

```toml
[verification]
enable_syntax_check = true        # L2: Python syntax validation
enable_test_count_check = true    # L3: Test count baseline check
enable_pytest_validation = true   # L3: Pytest output validation
enable_coverage_check = false     # L3: Coverage threshold check (future)
```

### Test Execution Settings

```toml
[verification]
test_command = "pytest"            # Command to run tests
test_timeout_seconds = 300         # Maximum test execution time
baseline_path = ".test_baseline"   # Path to test count baseline file
```

### Coverage Thresholds

```toml
[verification]
coverage_minimum_percent = 80.0           # Minimum line coverage (0-100)
coverage_branch_minimum_percent = 70.0    # Minimum branch coverage (0-100)
```

### Test Count Requirements

```toml
[verification]
minimum_test_count = 5             # Minimum number of tests required
allow_test_deletion = false        # Whether test count can decrease
```

### Performance Baselines

```toml
[verification]
max_execution_time_seconds = 60.0          # Max allowed execution time
performance_baseline_path = ".perf_baseline"  # Path to performance baseline
```

### Operation Modes

```toml
[verification]
strict_mode = false    # Fail on any warning
fail_fast = false      # Stop on first failure
verbose = false        # Enable verbose output
```

### Custom Settings

The configuration system supports arbitrary custom settings for extensibility:

```toml
[verification]
custom_key = "custom_value"
project_name = "my-project"
```

## Usage

### Python API

```python
from src.verification.config import VerificationConfig, load_config
from src.verification.runner import VerificationRunner

# Load from default search paths
config = load_config()

# Load from explicit path
config = load_config("path/to/config.toml")

# Create config programmatically
config = VerificationConfig(
    enable_syntax_check=True,
    coverage_minimum_percent=80.0,
    test_timeout_seconds=600
)

# Use with VerificationRunner
runner = VerificationRunner(config=config)
```

### Creating Config Files

Use the provided examples as starting points:
- `docs/verification.example.toml`
- `docs/verification.example.yaml`

Copy and customize for your project:

```bash
# TOML
cp docs/verification.example.toml .verification.toml

# YAML
cp docs/verification.example.yaml .verification.yaml
```

## Validation

Configuration values are validated when loaded:

- `test_timeout_seconds` must be positive
- Coverage percentages must be between 0 and 100
- `minimum_test_count` must be non-negative
- `max_execution_time_seconds` (if set) must be positive
- `test_command` cannot be empty

Invalid configurations raise `ValueError` with detailed error messages.

## Saving Configuration

```python
from src.verification.config import save_config, VerificationConfig

config = VerificationConfig(
    coverage_minimum_percent=80.0,
    test_timeout_seconds=600
)

# Save as TOML
save_config(config, ".verification.toml", format="toml")

# Save as YAML
save_config(config, ".verification.yaml", format="yaml")
```

## Dependencies

The configuration system requires:
- **tomli**: TOML reading (Python < 3.11)
- **tomli-w**: TOML writing
- **PyYAML**: YAML support

Install with:
```bash
pip install tomli tomli-w pyyaml
```

## Examples

### High Coverage Project

```toml
[verification]
enable_syntax_check = true
enable_test_count_check = true
enable_pytest_validation = true
enable_coverage_check = true

coverage_minimum_percent = 90.0
coverage_branch_minimum_percent = 85.0
minimum_test_count = 50
allow_test_deletion = false
strict_mode = true
```

### Fast CI Pipeline

```toml
[verification]
enable_syntax_check = true
enable_test_count_check = false
enable_pytest_validation = true

test_command = "pytest -x --tb=short"
test_timeout_seconds = 120
fail_fast = true
```

### Development Mode

```toml
[verification]
enable_syntax_check = true
enable_test_count_check = true
enable_pytest_validation = false

coverage_minimum_percent = 0.0
allow_test_deletion = true
verbose = true
```

## Backwards Compatibility

The VerificationRunner maintains backwards compatibility with existing code:

```python
# Old way (still works)
runner = VerificationRunner(verify_cmd="pytest -v", baseline_path=".custom_baseline")

# New way (recommended)
config = VerificationConfig(test_command="pytest -v", baseline_path=".custom_baseline")
runner = VerificationRunner(config=config)
```

When both constructor arguments and config are provided, config values take precedence.

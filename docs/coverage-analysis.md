# Coverage Analysis Integration

## Overview

The coverage analysis integration measures test coverage specifically on **changed files only**, using `coverage.py` and `pytest-cov`. This focused approach provides faster feedback and helps ensure new/modified code is properly tested.

## Features

- **Git integration**: Automatically detects changed Python files via `git diff`
- **Selective coverage**: Analyzes only modified files (not entire codebase)
- **Threshold enforcement**: Optional minimum coverage percentage requirements
- **Detailed reporting**: Per-file coverage with line-level details
- **Multi-file support**: Aggregates coverage across multiple changed files
- **Integration ready**: Works with existing `VerificationRunner` and config system

## Installation

Coverage.py is already installed:
```bash
pip install coverage  # Already installed
```

## Usage

### 1. Standalone Usage

```python
from src.verification.coverage_check import run_coverage_analysis

# Basic coverage analysis
passed, message, coverage_data = run_coverage_analysis(
    test_command="pytest",
    changed_files=["module.py"],
    min_coverage=80.0  # Optional threshold
)

print(f"Status: {passed}")
print(f"Coverage: {message}")
```

### 2. With VerificationRunner

Enable coverage in your verification config:

**YAML (.verification.yaml):**
```yaml
verification:
  enable_coverage_check: true
  coverage_minimum_percent: 80.0
  test_command: pytest
```

**TOML (.verification.toml):**
```toml
[verification]
enable_coverage_check = true
coverage_minimum_percent = 80.0
test_command = "pytest"
```

**Python:**
```python
from src.verification.runner import VerificationRunner
from src.verification.config import VerificationConfig

config = VerificationConfig(
    enable_coverage_check=True,
    coverage_minimum_percent=80.0
)

runner = VerificationRunner(config=config)
passed, output = runner.run(modified_files=["module.py"])
```

### 3. Convenience Functions

```python
from src.verification.coverage_check import check_coverage, get_coverage_report

# Check with threshold (pass/fail)
passed, message = check_coverage(
    changed_files=["module.py"],
    min_coverage=80.0
)

# Get detailed report (no threshold)
coverage_data = get_coverage_report(
    changed_files=["module.py"]
)

# Returns: {
#   "module.py": {
#     "percent_covered": 85.5,
#     "covered_lines": 17,
#     "total_lines": 20,
#     "missing_lines": [3, 5, 8]
#   }
# }
```

## API Reference

### `run_coverage_analysis(test_command, changed_files, min_coverage)`

Run coverage analysis on changed files.

**Parameters:**
- `test_command` (str): Command to run tests (default: "pytest")
- `changed_files` (List[str], optional): Files to analyze (auto-detects from git if None)
- `min_coverage` (float, optional): Minimum coverage threshold (0-100)

**Returns:**
- `passed` (bool): True if coverage meets requirements
- `message` (str): Human-readable status message
- `coverage_data` (dict): Per-file coverage details

### `check_coverage(changed_files, min_coverage, test_command)`

Convenience function for pass/fail check with threshold.

**Returns:**
- `passed` (bool)
- `message` (str)

### `get_coverage_report(changed_files, test_command)`

Get coverage data without threshold enforcement.

**Returns:**
- `coverage_data` (dict): Per-file coverage details

### `get_changed_files(base_ref)`

Get list of changed Python files from git.

**Parameters:**
- `base_ref` (str): Git reference to compare against (default: "HEAD")

**Returns:**
- List of changed Python file paths

## Configuration

Coverage settings in `VerificationConfig`:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enable_coverage_check` | bool | False | Enable coverage analysis |
| `coverage_minimum_percent` | float | 0.0 | Minimum coverage threshold (0-100) |
| `test_command` | str | "pytest" | Test command to run |

## Integration with Verification Pipeline

Coverage analysis runs as **L3 (Layer 3)** verification, after:
- L1: File existence check
- L2: Syntax validation
- L3: Pytest validation & test count checks

Order ensures fast failures for basic issues before running coverage analysis.

## Examples

### Example 1: CI Pipeline Integration

```python
from src.verification.coverage_check import check_coverage

# In CI, check coverage on changed files
changed_files = ["src/module1.py", "src/module2.py"]
passed, message = check_coverage(
    changed_files=changed_files,
    min_coverage=85.0,
    test_command="pytest tests/"
)

if not passed:
    print(f"Coverage check failed:\n{message}")
    exit(1)
```

### Example 2: Development Feedback

```python
from src.verification.coverage_check import get_coverage_report

# Get detailed coverage for review
coverage = get_coverage_report(changed_files=["mymodule.py"])

for file_path, data in coverage.items():
    print(f"{file_path}: {data['percent_covered']:.1f}%")
    if data['missing_lines']:
        print(f"  Uncovered lines: {data['missing_lines']}")
```

### Example 3: Full Verification Pipeline

```python
from src.verification.runner import VerificationRunner
from src.verification.config import VerificationConfig

config = VerificationConfig(
    enable_syntax_check=True,
    enable_test_count_check=True,
    enable_pytest_validation=True,
    enable_coverage_check=True,
    coverage_minimum_percent=80.0
)

runner = VerificationRunner(config=config)
passed, output = runner.run(modified_files=["src/module.py"])

print(output)  # Shows all layer results including coverage
```

## Error Handling

The implementation handles common errors gracefully:

- **No changed files**: Skips analysis, returns success
- **Git errors**: Returns empty file list
- **Coverage timeout**: Fails with timeout message (60s default)
- **Missing coverage data**: Reports 0% coverage for files not in report
- **Corrupted JSON**: Returns error with details

## Performance

- **Focused analysis**: Only analyzes changed files (faster than full coverage)
- **Timeout protection**: 60-second timeout prevents hangs
- **Minimal overhead**: ~1-2s for coverage report generation

## Testing

Comprehensive test suite in `test_verification_coverage.py`:

```bash
pytest test_verification_coverage.py -v
```

Tests cover:
- Git integration
- Coverage threshold enforcement
- Multi-file analysis
- Error handling
- Integration with VerificationRunner

## Future Enhancements

Potential improvements:
- Branch coverage support (currently line coverage only)
- Coverage trend tracking over time
- Differential coverage (only new lines)
- Integration with coverage services (Codecov, Coveralls)
- HTML report generation

## Troubleshooting

**Issue**: "Coverage analysis error: No such file or directory: '/tmp/coverage.json'"
**Solution**: Ensure coverage.py is installed and tests are runnable

**Issue**: "No changed Python files to analyze"
**Solution**: Make sure files are modified and saved (check `git diff`)

**Issue**: Low coverage on new files
**Solution**: Add tests for the new code before committing

**Issue**: Timeout during coverage analysis
**Solution**: Split large test suites or increase timeout (modify `timeout=60` in code)

# Language-Agnostic Verification

The verification system supports multiple programming languages through pluggable validators.

## Supported Languages

- **Python**: `py_compile`, `pytest`, `coverage.py`
- **JavaScript/TypeScript**: ESLint/tsc, Jest/Mocha, nyc/istanbul
- **.NET/C#**: `dotnet build`, `dotnet test`, coverlet

## Auto-Detection

The orchestrator automatically detects your project language from characteristic files:

| Language | Detection Files |
|----------|----------------|
| TypeScript | `tsconfig.json` |
| JavaScript | `package.json`, `package-lock.json`, `yarn.lock` |
| Python | `setup.py`, `pyproject.toml`, `requirements.txt`, `Pipfile` |
| .NET/C# | `*.csproj`, `*.sln` |

If no config files are found, it falls back to counting source file extensions.

## Usage

### Automatic (Recommended)

Let the system auto-detect your language:

```python
from src.verification import VerificationRunner

# Auto-detects language from project structure
runner = VerificationRunner()
passed, output = runner.run(modified_files=['src/main.ts', 'src/utils.ts'])
```

### Manual Configuration

Explicitly set the language via config file:

**`.verification.yaml`:**
```yaml
verification:
  language: typescript
  test_command: npm test
  coverage_minimum_percent: 80.0
```

**`.verification.toml`:**
```toml
[verification]
language = "javascript"
test_command = "yarn test"
coverage_minimum_percent = 75.0
```

### Programmatic

Override language detection programmatically:

```python
from src.verification import ValidatorFactory, Language
from src.verification.coordinator import LayerCoordinator

# Create factory for specific language
factory = ValidatorFactory(language=Language.TYPESCRIPT)

# Create coordinator with language-specific validators
coordinator = LayerCoordinator()
coordinator.register_language_aware_layers(
    language=Language.TYPESCRIPT,
    enable_syntax_check=True,
    enable_coverage=True,
    min_coverage=85.0,
    test_command="npm test"
)

# Run verification
passed, results = coordinator.run_layers(2, files=['src/app.ts'])
```

## Per-Language Examples

### Python Project

```yaml
# .verification.yaml
verification:
  language: python
  test_command: pytest
  enable_coverage_check: true
  coverage_minimum_percent: 80.0
```

Validators used:
- **L2 Syntax**: `py_compile` (checks `.py` files)
- **L3 Tests**: pytest validator (verifies tests ran)
- **L3 Coverage**: `coverage.py` + pytest

### TypeScript Project

```yaml
# .verification.yaml
verification:
  language: typescript
  test_command: npm test
  enable_coverage_check: true
  coverage_minimum_percent: 75.0
```

Validators used:
- **L2 Syntax**: `tsc --noEmit` or ESLint (checks `.ts`/`.tsx` files)
- **L3 Tests**: Jest/Mocha validator (parses test output)
- **L3 Coverage**: Jest coverage or nyc

### .NET/C# Project

```yaml
# .verification.yaml
verification:
  language: csharp  # or "dotnet"
  test_command: dotnet test
  enable_coverage_check: true
  coverage_minimum_percent: 80.0
```

Validators used:
- **L2 Syntax**: `dotnet build --no-restore` (checks `.cs` files)
- **L3 Tests**: dotnet test validator (parses test output)
- **L3 Coverage**: `dotnet test --collect:"XPlat Code Coverage"`

## Mixed-Language Projects

For projects with multiple languages, the system detects the primary language. You can:

1. Set language explicitly in config
2. Use file-specific detection:

```python
from src.verification.language_detector import detect_languages_in_files

# Detect languages from specific files
files = ['src/api.py', 'src/frontend/app.ts']
languages = detect_languages_in_files(files)
# Returns: [Language.PYTHON, Language.TYPESCRIPT]
```

## Adding New Languages

To add support for a new language:

1. **Create validators** in `src/verification/validators/`:
   - `<lang>_syntax.py` - Syntax checking layer
   - `<lang>_test.py` - Test validation layer
   - `<lang>_coverage.py` - Coverage analysis layer

2. **Update `language_detector.py`**:
   - Add language to `Language` enum
   - Add detection patterns to `DETECTION_PATTERNS`

3. **Update `validator_factory.py`**:
   - Import new validators
   - Add cases in `create_*` methods

4. **Write tests** in `tests/verification/`:
   - Test language detection
   - Test validator creation
   - Test validator behavior

See existing validators for reference patterns.

## Troubleshooting

### "No syntax checker available"

Install required tools:
- **TypeScript**: `npm install -D typescript` or `npm install -D eslint`
- **.NET**: Install .NET SDK

### "Unable to parse test output"

Ensure test command produces expected format:
- **Jest**: Should output "Tests: N passed, N total"
- **Mocha**: Should output "N passing"
- **dotnet test**: Should output "Total tests: N"

### Fallback to Python

If language detection fails, the system falls back to Python validators. To force a specific language:

```yaml
verification:
  language: typescript  # Explicit override
```

## Best Practices

1. **Let auto-detection work**: Only set `language` in config if detection fails
2. **Use language-specific test commands**: `npm test` for Node.js, `dotnet test` for .NET
3. **Match coverage thresholds to language norms**: Python often 80-90%, JS/TS often 70-80%
4. **Test validator behavior**: Validators gracefully skip if tools aren't installed

""".NET/C# syntax validation.

Validates C# syntax using dotnet build.
Provides immediate feedback on compilation errors.
"""

import subprocess
from pathlib import Path
from typing import List
from src.verification.layer import Layer, LayerResult, VerificationContext


class DotNetSyntaxLayer(Layer):
    """L2: .NET/C# syntax validation layer."""

    def __init__(self):
        """Initialize .NET syntax check layer."""
        super().__init__()

    @property
    def name(self) -> str:
        """Layer name."""
        return "DotNetSyntaxCheck"

    @property
    def level(self) -> int:
        """Layer level (L2)."""
        return 2

    def run(self, *, context: 'VerificationContext' = None, files: List[str] = None, **kwargs) -> LayerResult:
        """Validate C# syntax.

        Args:
            context: Optional VerificationContext with shared pipeline state
            files: List of file paths to check
            **kwargs: Ignored (for compatibility)

        Returns:
            LayerResult with validation status
        """
        if files is None and context is not None:
            files = context.modified_files
        if not files:
            return LayerResult(
                passed=True,
                message="No files to validate"
            )

        # Filter for C# files
        cs_files = [
            f for f in files
            if Path(f).suffix in ['.cs', '.csproj', '.sln']
            and Path(f).exists()
        ]

        if not cs_files:
            return LayerResult(
                passed=True,
                message="No C# files to validate"
            )

        # Find project/solution file
        project_file = self._find_project_file()
        if not project_file:
            return LayerResult(
                passed=True,
                message="No .csproj or .sln file found, skipping syntax check"
            )

        # Run dotnet build with --no-restore for faster syntax-only check
        try:
            result = subprocess.run(
                ['dotnet', 'build', project_file, '--no-restore', '/p:CheckForOverflowUnderflow=false'],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return LayerResult(
                    passed=True,
                    message="C# syntax valid (dotnet build succeeded)"
                )

            # Parse errors
            errors = []
            for line in result.stdout.split('\n') + result.stderr.split('\n'):
                if 'error CS' in line or 'error MSB' in line:
                    errors.append(line.strip())

            return LayerResult(
                passed=False,
                message="C# syntax check failed",
                error_details=errors[:10]  # Limit to first 10 errors
            )

        except subprocess.TimeoutExpired:
            return LayerResult(
                passed=False,
                message="dotnet build timed out",
                error_details=["Build took longer than 60 seconds"]
            )
        except FileNotFoundError:
            return LayerResult(
                passed=True,
                message="dotnet CLI not found, skipping syntax check"
            )
        except Exception as e:
            return LayerResult(
                passed=False,
                message=f"dotnet build failed: {str(e)}",
                error_details=[str(e)]
            )

    def _find_project_file(self) -> str:
        """Find .csproj or .sln file in current directory.

        Returns:
            Path to project/solution file, or empty string if not found
        """
        # Look for .sln first (preferred)
        sln_files = list(Path('.').glob('*.sln'))
        if sln_files:
            return str(sln_files[0])

        # Look for .csproj
        csproj_files = list(Path('.').glob('*.csproj'))
        if csproj_files:
            return str(csproj_files[0])

        # Look in subdirectories (one level deep)
        for item in Path('.').iterdir():
            if item.is_dir():
                csproj_files = list(item.glob('*.csproj'))
                if csproj_files:
                    return str(csproj_files[0])

        return ""

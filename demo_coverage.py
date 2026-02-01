#!/usr/bin/env python3
"""Demo: Coverage analysis for changed files.

This script demonstrates the coverage analysis integration.
"""

import tempfile
import os
from pathlib import Path
from src.verification.coverage_check import (
    get_changed_files,
    run_coverage_analysis,
    check_coverage,
    get_coverage_report
)


def demo_basic_coverage():
    """Demo: Basic coverage analysis."""
    print("=" * 60)
    print("DEMO 1: Basic Coverage Analysis")
    print("=" * 60)
    
    # Get changed files from git
    changed_files = get_changed_files()
    print(f"\n1. Detected {len(changed_files)} changed Python files")
    for f in changed_files[:5]:  # Show first 5
        print(f"   - {f}")
    
    # Run coverage analysis without threshold
    passed, message, coverage_data = run_coverage_analysis(
        test_command="pytest test_calculator.py",
        changed_files=["calculator.py"],
        min_coverage=None
    )
    
    print(f"\n2. Coverage Analysis Results:")
    print(f"   Status: {'PASSED' if passed else 'FAILED'}")
    print(f"   Message:\n{message}")
    print(f"\n   Coverage Data: {len(coverage_data)} files")


def demo_with_threshold():
    """Demo: Coverage with minimum threshold."""
    print("\n" + "=" * 60)
    print("DEMO 2: Coverage with Minimum Threshold (80%)")
    print("=" * 60)
    
    # Check coverage with 80% minimum
    passed, message = check_coverage(
        changed_files=["calculator.py"],
        min_coverage=80.0,
        test_command="pytest test_calculator.py"
    )
    
    print(f"\n1. Coverage Check (80% minimum):")
    print(f"   Status: {'PASSED' if passed else 'FAILED'}")
    print(f"   Message:\n{message}")


def demo_coverage_report():
    """Demo: Get coverage report without threshold."""
    print("\n" + "=" * 60)
    print("DEMO 3: Coverage Report (No Threshold)")
    print("=" * 60)
    
    # Get coverage report
    coverage_data = get_coverage_report(
        changed_files=["calculator.py"],
        test_command="pytest test_calculator.py"
    )
    
    print(f"\n1. Coverage Report:")
    for file_path, data in coverage_data.items():
        print(f"\n   File: {file_path}")
        print(f"   Coverage: {data['percent_covered']:.1f}%")
        print(f"   Lines: {data['covered_lines']}/{data['total_lines']}")
        if data['missing_lines']:
            print(f"   Missing lines: {data['missing_lines'][:10]}")


def demo_integration_with_runner():
    """Demo: Integration with VerificationRunner."""
    print("\n" + "=" * 60)
    print("DEMO 4: Integration with VerificationRunner")
    print("=" * 60)
    
    from src.verification.runner import VerificationRunner
    from src.verification.config import VerificationConfig
    
    # Create config with coverage enabled
    config = VerificationConfig(
        enable_coverage_check=True,
        coverage_minimum_percent=75.0,
        enable_syntax_check=True,
        enable_test_count_check=False,
        enable_pytest_validation=True
    )
    
    print("\n1. Config:")
    print(f"   Coverage enabled: {config.enable_coverage_check}")
    print(f"   Minimum coverage: {config.coverage_minimum_percent}%")
    
    # Create runner
    runner = VerificationRunner(config=config)
    
    print("\n2. Runner settings:")
    print(f"   Coverage check: {runner.enable_coverage_check}")
    print(f"   Min coverage: {runner.min_coverage}%")
    
    # Note: Full run would execute pytest with all layers
    print("\n   (Full run would execute all verification layers)")


if __name__ == '__main__':
    print("\nCoverage Analysis Integration Demo")
    print("=" * 60)
    
    try:
        demo_basic_coverage()
        demo_with_threshold()
        demo_coverage_report()
        demo_integration_with_runner()
        
        print("\n" + "=" * 60)
        print("Demo completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nDemo error: {e}")
        print("Note: Some demos require actual code changes to detect.")

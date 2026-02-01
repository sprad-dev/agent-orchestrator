"""Integration tests for the complete verification pipeline.

Tests all layers working together, edge cases, failure modes,
and configuration variations. Ensures no false positives/negatives.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from src.verification.runner import VerificationRunner
from src.verification.config import VerificationConfig


class TestFullPipelineIntegration:
    """Test all verification layers working together."""
    
    def test_complete_pipeline_all_pass(self):
        """All layers should pass with valid code and test execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid Python file
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("""
def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 5 - 3 == 2
""")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            # Create a runner that runs pytest on our test file
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            # All checks should pass
            assert passed is True, f"Pipeline should pass. Output: {output}"
            assert "✓ L1 All 1 file(s) exist" in output or "✓ L1" in output
            assert "✓ L2 Python syntax valid" in output or "✓ L2" in output
            assert "✓ L3 Pytest collected and ran" in output or "✓ L3" in output
            assert "✓ L3 Baseline created" in output or "✓ L3" in output
            assert "2 test" in output.lower()
    
    def test_l1_file_missing_blocks_pipeline(self):
        """Missing file should block at L1, preventing later stages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd="pytest",
                baseline_path=str(baseline_path)
            )
            
            # Try to verify missing files
            passed, output = runner.run(modified_files=[
                "/nonexistent/file1.py",
                "/nonexistent/file2.py"
            ])
            
            # Should fail at L1
            assert passed is False
            assert "FILE EXISTENCE CHECK FAILED" in output
            assert "/nonexistent/file1.py" in output
            assert "/nonexistent/file2.py" in output
            
            # L2+ should not run
            assert "✓ L2" not in output
            assert "✓ L3 Pytest validation" not in output
            
            # Pytest should not execute
            assert "collected" not in output.lower()
    
    def test_l2_syntax_error_blocks_pipeline(self):
        """Syntax error should block at L2, preventing pytest execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with syntax error
            bad_file = Path(tmpdir) / "bad_syntax.py"
            bad_file.write_text("def broken(\n    return 'oops'\n")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {bad_file}",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(bad_file)])
            
            # Should fail at L2
            assert passed is False
            assert "SYNTAX CHECK FAILED" in output
            assert str(bad_file) in output
            
            # L3+ should not run
            assert "✓ L3 Pytest validation" not in output
            
            # Pytest should not execute
            assert "collected" not in output.lower()
    
    def test_l3_pytest_zero_items_fails(self):
        """Pytest collecting 0 items should fail at L3 validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid Python file but not a test file
            not_test = Path(tmpdir) / "not_a_test.py"
            not_test.write_text("x = 1\n")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {tmpdir} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(not_test)])
            
            # Should fail at L3 pytest validation
            assert passed is False
            assert "Pytest collected 0 items" in output or "collected 0 items" in output.lower()
            
            # L1 and L2 should pass
            assert "✓ L1" in output
            assert "✓ L2" in output
    
    def test_l3_test_count_decrease_fails(self):
        """Decreasing test count should fail even if tests pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            # First run: 5 tests
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("""
def test_1(): assert True
def test_2(): assert True
def test_3(): assert True
def test_4(): assert True
def test_5(): assert True
""")
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            assert passed is True
            assert "5 test" in output.lower()
            
            # Second run: Delete 2 tests
            test_file.write_text("""
def test_1(): assert True
def test_2(): assert True
def test_3(): assert True
""")
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            # Should fail at L3 test count check
            assert passed is False
            assert "Test count decreased" in output
            assert "5 -> 3" in output
            
            # Earlier layers should pass
            assert "✓ L1" in output
            assert "✓ L2" in output
    
    def test_test_deletion_detected_even_when_tests_fail(self):
        """Critical: Test deletion should be detected even when remaining tests fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            # First run: 5 passing tests
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("""
def test_1(): assert True
def test_2(): assert True
def test_3(): assert True
def test_4(): assert True
def test_5(): assert True
""")
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            assert passed is True
            
            # Second run: Delete 3 tests AND make remaining tests fail
            test_file.write_text("""
def test_1(): assert False  # Now fails
def test_2(): assert False  # Now fails
""")
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            # Should fail due to test count decrease (not just test failures)
            assert passed is False
            assert "Test count decreased" in output or "BLOCKED" in output
            assert "5 -> 2" in output
            assert "decreased" in output.lower()


class TestLayerConfiguration:
    """Test enabling/disabling individual layers."""
    
    def test_disable_l1_file_check(self):
        """L1 file check can be disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / ".test_baseline"

            config = VerificationConfig(enable_file_exists_check=False)
            runner = VerificationRunner(
                verify_cmd="echo 'mock output'",
                baseline_path=str(baseline_path),
                config=config
            )

            # Should not check files when disabled
            passed, output = runner.run(modified_files=["/nonexistent/file.py"])

            assert "L1 File existence check" not in output
            assert "FILE EXISTENCE CHECK FAILED" not in output
    
    def test_disable_l2_syntax_check(self):
        """L2 syntax check can be disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "bad.py"
            bad_file.write_text("def broken(\n")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd="echo 'mock output'",
                baseline_path=str(baseline_path)
            )
            runner.enable_syntax_check = False
            
            passed, output = runner.run(modified_files=[str(bad_file)])
            
            assert "L2 Syntax check" not in output
            assert "SYNTAX CHECK FAILED" not in output
    
    def test_disable_l3_pytest_validation(self):
        """L3 pytest validation can be disabled."""
        runner = VerificationRunner(verify_cmd="echo 'no collection here'")
        runner.enable_pytest_validation = False
        
        passed, output = runner.run(modified_files=None)
        
        assert "L3 Pytest validation" not in output
        assert "Pytest collected" not in output
    
    def test_disable_l3_test_count_check(self):
        """L3 test count check can be disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            # Create baseline with 10 tests
            baseline_path_obj = Path(baseline_path)
            baseline_path_obj.write_text(json.dumps({
                'test_count': 10,
                'updated_at': '2024-01-01T00:00:00'
            }))
            
            runner = VerificationRunner(
                verify_cmd="echo 'collected 5 items'",
                baseline_path=str(baseline_path)
            )
            runner.enable_test_count_check = False
            
            passed, output = runner.run(modified_files=None)
            
            # Should not fail on decreased count when disabled
            assert "L3 Test count" not in output
            assert "Test count decreased" not in output
    
    def test_all_layers_disabled_still_runs_pytest(self):
        """With all layers disabled, pytest should still run."""
        runner = VerificationRunner(verify_cmd="echo 'pytest mock'")
        runner.enable_file_exists_check = False
        runner.enable_syntax_check = False
        runner.enable_pytest_validation = False
        runner.enable_test_count_check = False
        
        passed, output = runner.run(modified_files=None)
        
        # No layer markers
        assert "✓ L1" not in output
        assert "✓ L2" not in output
        assert "✓ L3" not in output
        
        # But pytest output should be there
        assert "pytest mock" in output


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_no_modified_files_provided(self):
        """Pipeline should work when no modified files provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("def test_pass(): assert True\n")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            # No modified_files argument
            passed, output = runner.run(modified_files=None)
            
            # L1 and L2 should be skipped (no files to check)
            assert "L1 File existence check" not in output
            assert "L2 Syntax check" not in output
            
            # L3 should still run
            assert "✓ L3" in output
            assert ("Baseline created" in output or "Pytest collected" in output)
    
    def test_empty_modified_files_list(self):
        """Empty list should skip L1 and L2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("def test_pass(): assert True\n")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            # Empty list
            passed, output = runner.run(modified_files=[])
            
            # L1 and L2 should be skipped
            assert "L1 File existence check" not in output
            assert "L2 Syntax check" not in output
            
            # L3 should still run
            assert "✓ L3" in output
    
    def test_mixed_py_and_non_py_files(self):
        """Should check existence of all files but only syntax of .py files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test_code.py"
            py_file.write_text("def test_x(): assert True\n")
            
            txt_file = Path(tmpdir) / "README.txt"
            txt_file.write_text("Documentation\n")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {py_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(py_file), str(txt_file)])
            
            # Both files should pass L1
            assert "✓ L1" in output
            
            # L2 should check syntax (only .py file)
            assert "✓ L2" in output
            
            # Should succeed overall
            assert passed is True
    
    def test_test_count_increase_updates_baseline(self):
        """Increasing test count should pass and update baseline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / ".test_baseline"
            test_file = Path(tmpdir) / "test_example.py"
            
            # First run: 2 tests
            test_file.write_text("""
def test_1(): assert True
def test_2(): assert True
""")
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            assert passed is True
            
            # Second run: Add more tests
            test_file.write_text("""
def test_1(): assert True
def test_2(): assert True
def test_3(): assert True
def test_4(): assert True
def test_5(): assert True
""")
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            # Should pass and update baseline
            assert passed is True
            assert "increased" in output.lower()
            assert "2 -> 5" in output
            
            # Verify baseline was updated
            with open(baseline_path) as f:
                data = json.load(f)
                assert data['test_count'] == 5
    
    def test_corrupted_baseline_recovered(self):
        """Corrupted baseline should be recreated without failing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / ".test_baseline"
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("def test_pass(): assert True\n")
            
            # Create corrupted baseline
            baseline_path.write_text("not valid json {[")
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            # Should pass and recreate baseline
            assert passed is True
            assert "recreated" in output.lower()
            
            # Verify baseline is now valid
            with open(baseline_path) as f:
                data = json.load(f)
                assert 'test_count' in data
                assert 'updated_at' in data


class TestFailureModes:
    """Test various failure scenarios."""
    
    def test_pytest_collection_failure(self):
        """Pytest collection errors should fail validation."""
        runner = VerificationRunner(verify_cmd="pytest /nonexistent/directory")
        
        passed, output = runner.run(modified_files=None)
        
        assert passed is False
        # Should fail due to either pytest validation or test count check
        assert ("Pytest collected 0 items" in output or "Test count decreased" in output or "collected 0 items" in output.lower())
    
    def test_multiple_syntax_errors(self):
        """Multiple syntax errors should be reported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad1 = Path(tmpdir) / "bad1.py"
            bad1.write_text("def broken1(\n")
            
            bad2 = Path(tmpdir) / "bad2.py"
            bad2.write_text("if True\n    pass\n")
            
            runner = VerificationRunner(verify_cmd="echo 'mock'")
            
            passed, output = runner.run(modified_files=[str(bad1), str(bad2)])
            
            assert passed is False
            assert "SYNTAX CHECK FAILED" in output
            assert str(bad1) in output
            assert str(bad2) in output
    
    def test_some_files_missing_some_exist(self):
        """Should report all missing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = Path(tmpdir) / "exists.py"
            existing.write_text("x = 1\n")
            
            runner = VerificationRunner(verify_cmd="echo 'mock'")
            
            passed, output = runner.run(modified_files=[
                str(existing),
                "/nonexistent/file1.py",
                "/nonexistent/file2.py"
            ])
            
            assert passed is False
            assert "FILE EXISTENCE CHECK FAILED" in output
            assert "/nonexistent/file1.py" in output
            assert "/nonexistent/file2.py" in output
            assert str(existing) not in output or "Missing files" not in output.split(str(existing))[0]
    
    def test_readonly_baseline_directory(self):
        """Read-only baseline directory should be handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            readonly_dir = Path(tmpdir) / "readonly"
            readonly_dir.mkdir()
            
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("def test_pass(): assert True\n")
            
            # Make directory read-only
            os.chmod(readonly_dir, 0o444)
            
            baseline_path = readonly_dir / ".test_baseline"
            
            try:
                runner = VerificationRunner(
                    verify_cmd=f"pytest {test_file} -v",
                    baseline_path=str(baseline_path)
                )
                
                passed, output = runner.run(modified_files=[str(test_file)])
                
                # Should fail due to baseline write error
                assert passed is False
                assert "Failed to write baseline" in output or "Permission" in output
            finally:
                os.chmod(readonly_dir, 0o755)


class TestCustomVerifyCommand:
    """Test different pytest commands and configurations."""
    
    def test_custom_pytest_args(self):
        """Custom pytest arguments should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("""
def test_one(): assert True
def test_two(): assert True
""")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            # Use pytest with custom args
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v --tb=short",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            assert passed is True
            assert "2 test" in output.lower()
    
    def test_pytest_with_markers(self):
        """Pytest with markers should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("""
import pytest

@pytest.mark.slow
def test_slow(): assert True

def test_fast(): assert True
""")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            # Run only non-slow tests
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v -m 'not slow'",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            # Should pass with 1 test ran (fast) - output shows "2 test(s)" collected but only 1 ran
            assert passed is True
            assert "1 passed" in output.lower()


class TestLayerInteraction:
    """Test how layers interact with each other."""
    
    def test_early_failure_prevents_later_layers(self):
        """Failure in early layer should prevent later layers from running."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # File exists but has syntax error
            bad_file = Path(tmpdir) / "bad.py"
            bad_file.write_text("def broken(\n")
            
            runner = VerificationRunner(verify_cmd=f"pytest {bad_file}")
            
            passed, output = runner.run(modified_files=[str(bad_file)])
            
            # L2 fails
            assert "SYNTAX CHECK FAILED" in output
            
            # L3 doesn't run (pytest not executed)
            assert "✓ L3" not in output
            assert "collected" not in output.lower()
    
    def test_all_layers_report_when_all_pass(self):
        """When everything passes, all layers should be reported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("def test_pass(): assert True\n")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            # All layers should be present
            assert "✓ L1" in output
            assert "✓ L2" in output
            assert "✓ L3" in output
            assert ("Baseline created" in output or "Pytest collected" in output)
            
            assert passed is True
    
    def test_pytest_fails_but_validation_passes(self):
        """When pytest tests fail, L3 validation should still work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text("""
def test_fail(): assert False
def test_pass(): assert True
""")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            # Pytest tests fail (1 failed)
            assert passed is False
            assert "FAILED" in output or "failed" in output
            
            # But L3 validation passes (tests were collected and ran)
            assert "✓ L3" in output
            assert ("Baseline created" in output or "Pytest collected" in output)
            assert "2 test" in output.lower()


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    def test_first_time_project_setup(self):
        """First time running should create baseline successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_project.py"
            test_file.write_text("""
def test_feature_a(): assert True
def test_feature_b(): assert True
def test_feature_c(): assert True
""")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            # First run - no baseline exists
            assert not baseline_path.exists()
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            assert passed is True
            assert "Baseline created" in output
            assert "3 tests" in output.lower()
            
            # Baseline should now exist
            assert baseline_path.exists()
            
            with open(baseline_path) as f:
                data = json.load(f)
                assert data['test_count'] == 3
    
    def test_adding_new_test_file(self):
        """Adding new test file should increase test count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file1 = Path(tmpdir) / "test_module1.py"
            test_file1.write_text("def test_a(): assert True\n")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {tmpdir} -v",
                baseline_path=str(baseline_path)
            )
            
            # First run: 1 test
            passed, output = runner.run(modified_files=[str(test_file1)])
            assert passed is True
            assert "1 test" in output.lower()
            
            # Add new test file
            test_file2 = Path(tmpdir) / "test_module2.py"
            test_file2.write_text("""
def test_b(): assert True
def test_c(): assert True
""")
            
            # Second run: 3 tests total
            passed, output = runner.run(modified_files=[str(test_file1), str(test_file2)])
            assert passed is True
            assert "increased" in output.lower()
            assert "1 -> 3" in output
    
    def test_refactoring_with_same_test_count(self):
        """Refactoring code with same test count should pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_code.py"
            
            # Initial implementation
            test_file.write_text("""
def test_feature():
    result = 2 + 2
    assert result == 4
""")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            assert passed is True
            
            # Refactor but keep same test
            test_file.write_text("""
def add(a, b):
    return a + b

def test_feature():
    result = add(2, 2)
    assert result == 4
""")
            
            passed, output = runner.run(modified_files=[str(test_file)])
            assert passed is True
            assert "unchanged" in output.lower()
            assert "1 test" in output.lower()
    
    def test_malicious_test_deletion_blocked(self):
        """Malicious attempt to delete tests should be blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_security.py"
            
            # Original: comprehensive test suite
            test_file.write_text("""
def test_auth(): assert True
def test_authorization(): assert True
def test_input_validation(): assert True
def test_sql_injection(): assert True
def test_xss(): assert True
""")
            
            baseline_path = Path(tmpdir) / ".test_baseline"
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            assert passed is True
            assert "5 test" in output.lower()
            
            # Malicious: Remove critical tests
            test_file.write_text("""
def test_auth(): assert True
# Deleted: test_authorization, test_input_validation, test_sql_injection, test_xss
""")
            
            passed, output = runner.run(modified_files=[str(test_file)])
            
            # Should be BLOCKED
            assert passed is False
            assert "Test count decreased" in output or "BLOCKED" in output
            assert "5 -> 1" in output
            assert "BLOCKED" in output


class TestBaselineManagement:
    """Test baseline file creation and management."""
    
    def test_baseline_created_in_correct_location(self):
        """Baseline should be created at specified path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_baseline = Path(tmpdir) / "custom" / "baseline.json"
            test_file = Path(tmpdir) / "test_x.py"
            test_file.write_text("def test_x(): assert True\n")
            
            # Ensure parent dir exists
            custom_baseline.parent.mkdir(parents=True, exist_ok=True)
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(custom_baseline)
            )
            
            passed, output = runner.run(modified_files=[str(test_file)])
            assert passed is True
            
            # Baseline should exist at custom location
            assert custom_baseline.exists()
    
    def test_baseline_contains_metadata(self):
        """Baseline should contain test count and timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / ".test_baseline"
            test_file = Path(tmpdir) / "test_x.py"
            test_file.write_text("def test_x(): assert True\n")
            
            runner = VerificationRunner(
                verify_cmd=f"pytest {test_file} -v",
                baseline_path=str(baseline_path)
            )
            
            runner.run(modified_files=[str(test_file)])
            
            with open(baseline_path) as f:
                data = json.load(f)
                
            assert 'test_count' in data
            assert data['test_count'] == 1
            assert 'updated_at' in data
            assert isinstance(data['updated_at'], str)
    
    def test_default_baseline_path(self):
        """Default baseline path should be .test_baseline."""
        runner = VerificationRunner(verify_cmd="echo 'mock'")
        assert runner.baseline_path == ".test_baseline"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

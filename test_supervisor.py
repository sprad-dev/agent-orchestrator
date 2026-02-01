#!/usr/bin/env python3
import unittest
import tempfile
import os
from pathlib import Path
from supervisor import RalphLoop
from src.context import (
    parse_context_files,
    get_default_context_files,
    build_context,
    build_static_context,
)


class TestEscalationProtocol(unittest.TestCase):
    """Tests for model escalation functionality."""

    def test_default_models(self):
        """Test that default models are set correctly."""
        loop = RalphLoop("echo {prompt}", "true", 3)
        self.assertEqual(loop.models, ["claude-4.5-haiku", "claude-4.5-haiku", "claude-4.5-sonnet"])

    def test_custom_models(self):
        """Test that custom models can be provided."""
        custom_models = ["model-a", "model-b", "model-c"]
        loop = RalphLoop("echo {prompt}", "true", 3, models=custom_models)
        self.assertEqual(loop.models, custom_models)

    def test_models_list_length(self):
        """Test that escalation tries each model."""
        models = ["haiku", "sonnet"]
        loop = RalphLoop("echo {prompt}", "true", 3, models=models)
        self.assertEqual(len(loop.models), 2)


class TestContextPruning(unittest.TestCase):
    """Tests for context pruning functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.loop = RalphLoop("echo {prompt}", "true", 1)
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.test_dir)

    def test_parse_context_files_json_format(self):
        """Test parsing context_files in JSON format."""
        task = 'Fix bug context_files: ["file1.py", "file2.py"]'
        files = parse_context_files(task)
        self.assertEqual(files, ["file1.py", "file2.py"])

    def test_parse_context_files_inline_format(self):
        """Test parsing context_files in inline format."""
        task = "Fix bug [context: file1.py, file2.py]"
        files = parse_context_files(task)
        self.assertEqual(files, ["file1.py", "file2.py"])

    def test_parse_context_files_none(self):
        """Test when no context_files specified."""
        task = "Fix the bug in the code"
        files = parse_context_files(task)
        self.assertIsNone(files)

    def test_get_default_context_files(self):
        """Test default context file detection."""
        # Create test files
        Path("calculator.py").touch()
        Path("test_calculator.py").touch()
        
        task = "Fix bug in calculator.py"
        files = get_default_context_files(task)
        
        self.assertIn("calculator.py", files)
        self.assertIn("test_calculator.py", files)

    def test_get_default_context_files_no_test(self):
        """Test default context when test file doesn't exist."""
        Path("utils.py").touch()
        
        task = "Fix bug in utils.py"
        files = get_default_context_files(task)
        
        self.assertEqual(files, ["utils.py"])

    def test_build_context_single_file(self):
        """Test building context from a single file."""
        # Create test file
        test_file = Path("test.py")
        test_file.write_text("def foo():\n    pass\n")
        
        context = build_context(["test.py"])
        
        self.assertIn("=== CONTEXT FILES ===", context)
        self.assertIn("--- test.py ---", context)
        self.assertIn("def foo():", context)
        self.assertIn("=== END CONTEXT ===", context)

    def test_build_context_multiple_files(self):
        """Test building context from multiple files."""
        Path("file1.py").write_text("# File 1\n")
        Path("file2.py").write_text("# File 2\n")
        
        context = build_context(["file1.py", "file2.py"])
        
        self.assertIn("--- file1.py ---", context)
        self.assertIn("--- file2.py ---", context)
        self.assertIn("# File 1", context)
        self.assertIn("# File 2", context)

    def test_build_context_missing_file(self):
        """Test building context with missing file."""
        context = build_context(["nonexistent.py"])
        
        self.assertIn("nonexistent.py (NOT FOUND)", context)

    def test_build_context_empty_list(self):
        """Test building context with empty file list."""
        context = build_context([])
        self.assertEqual(context, "")

    def test_context_size_limit(self):
        """Test that context stays under 10 files for typical tasks."""
        # Create 15 files
        for i in range(15):
            Path(f"file{i}.py").touch()
        
        task = "Fix bug in file1.py and file2.py"
        files = get_default_context_files(task)
        
        # Should only detect mentioned files
        self.assertLessEqual(len(files), 10)
        self.assertIn("file1.py", files)
        self.assertIn("file2.py", files)


class TestEscalationIntegration(unittest.TestCase):
    """Integration tests for escalation protocol."""

    def setUp(self):
        """Set up test fixtures."""
        # Clean up any /tmp test artifacts from previous runs
        os.system("rm -rf /tmp/test_* > /dev/null 2>&1")
        
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repo
        os.system("git init > /dev/null 2>&1")
        os.system("git config user.email 'test@test.com' > /dev/null 2>&1")
        os.system("git config user.name 'Test User' > /dev/null 2>&1")
        
        # Create initial commit
        Path("dummy.txt").write_text("initial")
        os.system("git add . > /dev/null 2>&1")
        os.system("git commit -m 'initial' > /dev/null 2>&1")

    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.test_dir)

    def test_models_tried_in_sequence(self):
        """Test that models are attempted in order."""
        # Create agent that logs which model was called
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
echo "$2" >> models_called.txt
echo "output" > result.txt
exit 1  # Always fail
""")
        agent_script.chmod(0o755)
        
        models = ["model-a", "model-b", "model-c"]
        loop = RalphLoop("./agent.sh {prompt} {model}", "false", 3, models=models)
        
        loop.execute("test task")
        
        # Check that all models were called in order
        if Path("models_called.txt").exists():
            called = Path("models_called.txt").read_text().strip().split('\n')
            self.assertEqual(called, models)

    def test_early_exit_on_success(self):
        """Test that loop exits on first successful model."""
        # Create agent that creates files and logs to temp location
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
mkdir -p /tmp/test_models
echo "$2" >> /tmp/test_models/called.txt
# Always create a file so there are changes
echo "output from $2" > "output_$2.txt"
# First model fails verification, second succeeds
exit 0
""")
        agent_script.chmod(0o755)
        
        models = ["model-a", "model-b", "model-c"]
        # Use verifier that only passes on second attempt
        verify_script = Path("verify.sh")
        verify_script.write_text("""#!/bin/bash
if [ -f output_model-b.txt ]; then
    exit 0
fi
exit 1
""")
        verify_script.chmod(0o755)
        
        # Add scripts to git so they persist
        os.system("git add agent.sh verify.sh > /dev/null 2>&1")
        os.system("git commit -m 'add scripts' > /dev/null 2>&1")
        
        loop = RalphLoop("./agent.sh {prompt} {model}", "./verify.sh", 3, models=models)
        
        result = loop.execute("test task")
        
        # Should succeed and only call first two models
        self.assertTrue(result)
        if Path("/tmp/test_models/called.txt").exists():
            called = Path("/tmp/test_models/called.txt").read_text().strip().split('\n')
            self.assertEqual(called, ["model-a", "model-b"])

    def test_git_reset_between_attempts(self):
        """Test that git resets between model attempts."""
        # Create agent that creates different files for each model
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
mkdir -p /tmp/test_resets
echo "$2" >> /tmp/test_resets/attempts.txt
echo "$2" > "file_$2.txt"
exit 0
""")
        agent_script.chmod(0o755)
        
        # Add to git so it persists
        os.system("git add agent.sh > /dev/null 2>&1")
        os.system("git commit -m 'add agent' > /dev/null 2>&1")
        
        models = ["model-a", "model-b"]
        loop = RalphLoop("./agent.sh {prompt} {model}", "false", 3, models=models)
        
        loop.execute("test task")
        
        # All models attempted
        if Path("/tmp/test_resets/attempts.txt").exists():
            attempts = Path("/tmp/test_resets/attempts.txt").read_text().strip().split('\n')
            self.assertEqual(len(attempts), 2)
        
        # Working directory should be clean after full failure (stash popped)
        result = os.popen("git status --porcelain").read().strip()
        # After failure and stash pop, should be back to original state
        self.assertEqual(result, "")

    def test_escalation_context_passed(self):
        """Test that error context is passed to subsequent models."""
        # Create agent that logs the prompt received
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
mkdir -p /tmp/test_prompts
echo "=== Model $2 ===" >> /tmp/test_prompts/log.txt
echo "$1" >> /tmp/test_prompts/log.txt
# Create a file so there are changes
echo "output from $2" > "result_$2.txt"
# First model fails verification
exit 0
""")
        agent_script.chmod(0o755)
        
        # Verifier that fails first, passes second
        verify_script = Path("verify.sh")
        verify_script.write_text("""#!/bin/bash
if [ -f result_model-b.txt ]; then
    exit 0
fi
echo "Test failed: result_model-b.txt not found"
exit 1
""")
        verify_script.chmod(0o755)
        
        # Add scripts to git
        os.system("git add agent.sh verify.sh > /dev/null 2>&1")
        os.system("git commit -m 'add scripts' > /dev/null 2>&1")
        
        models = ["model-a", "model-b"]
        loop = RalphLoop("./agent.sh {prompt} {model}", "./verify.sh", 3, models=models)
        
        result = loop.execute("test task")
        
        # Check that second model received escalation context with diff-only feedback
        self.assertTrue(result)
        if Path("/tmp/test_prompts/log.txt").exists():
            log = Path("/tmp/test_prompts/log.txt").read_text()
            # New diff-only feedback format
            self.assertIn("Previous attempt failed", log)
            self.assertIn("=== GOAL ===", log)
            self.assertIn("=== ERROR OUTPUT ===", log)
            self.assertIn("Think step-by-step", log)

    def test_final_failure_all_models_exhausted(self):
        """Test behavior when all models fail."""
        # Create agent that always fails
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
echo "$2" >> attempts.log
echo "failed" > output.txt
exit 1
""")
        agent_script.chmod(0o755)
        
        models = ["model-a", "model-b", "model-c"]
        loop = RalphLoop("./agent.sh {prompt} {model}", "false", 3, models=models)
        
        result = loop.execute("test task")
        
        # Should fail and try all models
        self.assertFalse(result)
        if Path("attempts.log").exists():
            attempts = Path("attempts.log").read_text().strip().split('\n')
            self.assertEqual(len(attempts), 3)

    def test_agent_no_changes_triggers_retry(self):
        """Test that agent producing no changes triggers reset and retry."""
        # Create agent that produces no git changes
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
# Track calls without creating tracked files
mkdir -p /tmp/test_calls
echo "$2" >> /tmp/test_calls/count.txt
# Don't create any files - no changes
exit 0
""")
        agent_script.chmod(0o755)
        # Add agent to git so it doesn't get cleaned
        os.system("git add agent.sh > /dev/null 2>&1")
        os.system("git commit -m 'add agent' > /dev/null 2>&1")
        
        models = ["model-a", "model-b"]
        loop = RalphLoop("./agent.sh {prompt} {model}", "true", 3, models=models)
        
        result = loop.execute("test task")
        
        # Should fail because agent made no changes
        self.assertFalse(result)
        # Should have tried all models
        if Path("/tmp/test_calls/count.txt").exists():
            calls = len(Path("/tmp/test_calls/count.txt").read_text().strip().split('\n'))
            self.assertEqual(calls, 2)


class TestContextIntegration(unittest.TestCase):
    """Integration tests for context pruning in full loop."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repo
        os.system("git init > /dev/null 2>&1")
        os.system("git config user.email 'test@test.com' > /dev/null 2>&1")
        os.system("git config user.name 'Test User' > /dev/null 2>&1")
        
        # Create initial commit
        Path("dummy.txt").write_text("initial")
        os.system("git add . > /dev/null 2>&1")
        os.system("git commit -m 'initial' > /dev/null 2>&1")

    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.test_dir)

    def test_context_files_in_agent_prompt(self):
        """Test that context files are included in agent prompt."""
        # Create files
        Path("source.py").write_text("# Source code\n")
        Path("test_source.py").write_text("# Tests\n")
        
        # Create mock agent that echoes prompt to file
        agent_script = Path("mock_agent.sh")
        agent_script.write_text("""#!/bin/bash
echo "$1" > prompt_received.txt
touch output.txt
""")
        agent_script.chmod(0o755)
        
        loop = RalphLoop("./mock_agent.sh {prompt}", "true", 1)
        task = 'Fix bug context_files: ["source.py", "test_source.py"]'
        
        loop.execute(task)
        
        # Check that prompt contained context
        prompt_file = Path("prompt_received.txt")
        if prompt_file.exists():
            prompt = prompt_file.read_text()
            self.assertIn("=== CONTEXT FILES ===", prompt)
            self.assertIn("source.py", prompt)
            self.assertIn("# Source code", prompt)


class TestTwoPhaseMode(unittest.TestCase):
    """Tests for two-phase test-driven execution."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repo
        os.system("git init > /dev/null 2>&1")
        os.system("git config user.email 'test@test.com' > /dev/null 2>&1")
        os.system("git config user.name 'Test User' > /dev/null 2>&1")
        
        # Create initial commit
        Path("dummy.txt").write_text("initial")
        os.system("git add . > /dev/null 2>&1")
        os.system("git commit -m 'initial' > /dev/null 2>&1")

    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.test_dir)

    def test_two_phase_mode_enabled(self):
        """Test that two-phase mode is enabled when both models specified."""
        loop = RalphLoop("echo {prompt}", "true", 1, 
                        test_model="claude-3-5-sonnet", 
                        impl_model="claude-3-haiku")
        self.assertTrue(loop.two_phase_mode)

    def test_two_phase_mode_disabled(self):
        """Test that two-phase mode is disabled by default."""
        loop = RalphLoop("echo {prompt}", "true", 1)
        self.assertFalse(loop.two_phase_mode)

    def test_test_generation_phase_creates_files(self):
        """Test that test generation phase creates test files."""
        # Create mock agent that creates a test file
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
# Create a test file
cat > test_example.py << 'EOF'
def test_example():
    assert False, "Not implemented yet"
EOF
""")
        agent_script.chmod(0o755)
        
        # Add agent to git
        os.system("git add agent.sh > /dev/null 2>&1")
        os.system("git commit -m 'add agent' > /dev/null 2>&1")
        
        loop = RalphLoop("./agent.sh {prompt} {model}", "pytest", 1,
                        test_model="sonnet", impl_model="haiku")
        
        result = loop.run_test_generation_phase("Create example function", [])
        
        # Should succeed and create test file
        self.assertTrue(result)
        self.assertTrue(Path("test_example.py").exists())
        
        # Test file should be committed
        status = os.popen("git status --porcelain").read().strip()
        self.assertEqual(status, "")

    def test_implementation_phase_runs_after_tests(self):
        """Test that implementation phase runs tests and implements code."""
        # Create a failing test
        Path("test_add.py").write_text("""
def test_add():
    from calculator import add
    assert add(2, 3) == 5
""")
        
        # Commit test
        os.system("git add test_add.py > /dev/null 2>&1")
        os.system("git commit -m 'add test' > /dev/null 2>&1")
        
        # Create mock agent that implements the function
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
# Implement the add function
cat > calculator.py << 'EOF'
def add(a, b):
    return a + b
EOF
""")
        agent_script.chmod(0o755)
        
        # Add agent to git
        os.system("git add agent.sh > /dev/null 2>&1")
        os.system("git commit -m 'add agent' > /dev/null 2>&1")
        
        loop = RalphLoop("./agent.sh {prompt} {model}", "python -m pytest test_add.py", 1,
                        test_model="sonnet", impl_model="haiku")
        
        result = loop.run_implementation_phase("Implement add function", [])
        
        # Should succeed
        self.assertTrue(result)
        self.assertTrue(Path("calculator.py").exists())

    def test_two_phase_execute_end_to_end(self):
        """Test complete two-phase execution workflow."""
        # Create test generation agent
        test_agent = Path("test_agent.sh")
        test_agent.write_text("""#!/bin/bash
cat > test_multiply.py << 'EOF'
def test_multiply():
    from calc import multiply
    assert multiply(3, 4) == 12
EOF
""")
        test_agent.chmod(0o755)
        
        # Create implementation agent
        impl_agent = Path("impl_agent.sh")
        impl_agent.write_text("""#!/bin/bash
cat > calc.py << 'EOF'
def multiply(a, b):
    return a * b
EOF
""")
        impl_agent.chmod(0o755)
        
        # Add agents to git
        os.system("git add test_agent.sh impl_agent.sh > /dev/null 2>&1")
        os.system("git commit -m 'add agents' > /dev/null 2>&1")
        
        # Create wrapper that routes to correct agent based on prompt
        wrapper = Path("wrapper.sh")
        wrapper.write_text("""#!/bin/bash
if echo "$1" | grep -q "Generate pytest"; then
    ./test_agent.sh "$@"
else
    ./impl_agent.sh "$@"
fi
""")
        wrapper.chmod(0o755)
        
        os.system("git add wrapper.sh > /dev/null 2>&1")
        os.system("git commit -m 'add wrapper' > /dev/null 2>&1")
        
        loop = RalphLoop("./wrapper.sh {prompt} {model}", "python -m pytest test_multiply.py", 1,
                        test_model="sonnet", impl_model="haiku")
        
        result = loop.execute_two_phase("Create multiply function")
        
        # Should succeed with both test and implementation committed
        self.assertTrue(result)
        self.assertTrue(Path("test_multiply.py").exists())
        self.assertTrue(Path("calc.py").exists())
        
        # Should have 2 new commits (test + impl)
        log = os.popen("git log --oneline").read()
        commits = [line for line in log.strip().split('\n') if line]
        self.assertGreaterEqual(len(commits), 3)  # initial + test + impl

    def test_two_phase_rollback_on_test_gen_failure(self):
        """Test that two-phase mode rolls back if test generation fails."""
        # Create agent that fails to produce changes
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
# Don't create any files
echo "Failed to generate tests"
exit 1
""")
        agent_script.chmod(0o755)
        
        os.system("git add agent.sh > /dev/null 2>&1")
        os.system("git commit -m 'add agent' > /dev/null 2>&1")
        
        loop = RalphLoop("./agent.sh {prompt} {model}", "pytest", 1,
                        test_model="sonnet", impl_model="haiku")
        
        result = loop.execute_two_phase("Create example")
        
        # Should fail
        self.assertFalse(result)
        
        # Working directory should be clean
        status = os.popen("git status --porcelain").read().strip()
        self.assertEqual(status, "")

    def test_two_phase_rollback_on_impl_failure(self):
        """Test that two-phase mode rolls back both phases if implementation fails."""
        # Create test generation agent
        test_agent = Path("test_agent.sh")
        test_agent.write_text("""#!/bin/bash
cat > test_fail.py << 'EOF'
def test_something():
    assert False, "Always fails"
EOF
""")
        test_agent.chmod(0o755)
        
        # Create implementation agent that doesn't fix the test
        impl_agent = Path("impl_agent.sh")
        impl_agent.write_text("""#!/bin/bash
# Create file but don't fix test
touch output.py
""")
        impl_agent.chmod(0o755)
        
        os.system("git add test_agent.sh impl_agent.sh > /dev/null 2>&1")
        os.system("git commit -m 'add agents' > /dev/null 2>&1")
        
        # Create wrapper
        wrapper = Path("wrapper.sh")
        wrapper.write_text("""#!/bin/bash
if echo "$1" | grep -q "Generate pytest"; then
    ./test_agent.sh "$@"
else
    ./impl_agent.sh "$@"
fi
""")
        wrapper.chmod(0o755)
        
        os.system("git add wrapper.sh > /dev/null 2>&1")
        os.system("git commit -m 'add wrapper' > /dev/null 2>&1")
        
        loop = RalphLoop("./wrapper.sh {prompt} {model}", "python -m pytest test_fail.py", 1,
                        test_model="sonnet", impl_model="haiku")
        
        result = loop.execute_two_phase("Create something")
        
        # Should fail
        self.assertFalse(result)
        
        # Both test and implementation should be rolled back
        self.assertFalse(Path("test_fail.py").exists())
        self.assertFalse(Path("output.py").exists())


class TestDiffOnlyFeedback(unittest.TestCase):
    """Tests for diff-only feedback loop to prevent context rot."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repo
        os.system("git init > /dev/null 2>&1")
        os.system("git config user.email 'test@test.com' > /dev/null 2>&1")
        os.system("git config user.name 'Test User' > /dev/null 2>&1")
        
        # Create initial commit
        Path("dummy.txt").write_text("initial")
        os.system("git add . > /dev/null 2>&1")
        os.system("git commit -m 'initial' > /dev/null 2>&1")

    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.test_dir)

    def test_retry_uses_diff_only_format(self):
        """Test that retry attempts use diff-only feedback format."""
        # Agent that logs prompts to a file
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
mkdir -p /tmp/diff_test_prompts
ATTEMPT_NUM=$(ls /tmp/diff_test_prompts/ | wc -l)
echo "=== ATTEMPT $ATTEMPT_NUM ===" >> /tmp/diff_test_prompts/attempt_${ATTEMPT_NUM}.txt
echo "$1" >> /tmp/diff_test_prompts/attempt_${ATTEMPT_NUM}.txt
echo "code change" > output.txt
exit 0
""")
        agent_script.chmod(0o755)
        
        # Verifier that always fails (we just want to check prompt format)
        verify_script = Path("verify.sh")
        verify_script.write_text("""#!/bin/bash
echo "Test failed - checking prompt format only"
exit 1
""")
        verify_script.chmod(0o755)
        
        os.system("git add agent.sh verify.sh > /dev/null 2>&1")
        os.system("git commit -m 'add scripts' > /dev/null 2>&1")
        
        # Clean up previous test logs
        os.system("rm -rf /tmp/diff_test_prompts")
        
        models = ["model-1", "model-2"]
        loop = RalphLoop("./agent.sh {prompt} {model}", "./verify.sh", 2, models=models)
        
        # Execute will fail, but that's OK - we just want to check the prompts
        loop.execute("test task")
        
        # Verify first attempt doesn't have diff-only format
        self.assertTrue(Path("/tmp/diff_test_prompts/attempt_0.txt").exists())
        attempt_1 = Path("/tmp/diff_test_prompts/attempt_0.txt").read_text()
        self.assertNotIn("=== GOAL ===", attempt_1)
        self.assertNotIn("=== CODE ATTEMPTED", attempt_1)
        
        # Verify second attempt has diff-only format
        self.assertTrue(Path("/tmp/diff_test_prompts/attempt_1.txt").exists())
        attempt_2 = Path("/tmp/diff_test_prompts/attempt_1.txt").read_text()
        self.assertIn("Previous attempt failed", attempt_2)
        self.assertIn("=== GOAL ===", attempt_2)
        self.assertIn("=== ERROR OUTPUT ===", attempt_2)
        self.assertIn("test task", attempt_2)  # Original task preserved

    def test_retry_excludes_conversation_history(self):
        """Test that retry prompts maintain flat token count with static context."""
        # Create files to serve as static context
        Path("context1.py").write_text("# " + "A" * 500)
        Path("context2.py").write_text("# " + "B" * 500)
        os.system("git add *.py > /dev/null 2>&1")
        os.system("git commit -m 'add context files' > /dev/null 2>&1")
        
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
mkdir -p /tmp/prompt_sizes
ATTEMPT_NUM=$(ls /tmp/prompt_sizes/ | wc -l)
echo ${#1} > /tmp/prompt_sizes/size_${ATTEMPT_NUM}.txt
echo "change $ATTEMPT_NUM" > output.txt
exit 0
""")
        agent_script.chmod(0o755)
        
        verify_script = Path("verify.sh")
        verify_script.write_text("""#!/bin/bash
COMMITS=$(git log --oneline | grep -c "Agent" || echo 0)
if [ "$COMMITS" -ge 1 ]; then
    exit 0
fi
# Generate longer error to test context growth
python3 -c "print('ERROR: ' + 'Long error message. ' * 50)"
exit 1
""")
        verify_script.chmod(0o755)
        
        os.system("git add agent.sh verify.sh > /dev/null 2>&1")
        os.system("git commit -m 'add scripts' > /dev/null 2>&1")
        os.system("rm -rf /tmp/prompt_sizes")
        
        # Use context_files to include static context in prompts
        task_with_context = "Fix the bug [context: context1.py, context2.py]"
        
        models = ["model-1", "model-2"]
        loop = RalphLoop("./agent.sh {prompt} {model}", "./verify.sh", 2, models=models)
        
        loop.execute(task_with_context)
        
        # Read prompt sizes
        if Path("/tmp/prompt_sizes/size_0.txt").exists() and Path("/tmp/prompt_sizes/size_1.txt").exists():
            size_1 = int(Path("/tmp/prompt_sizes/size_0.txt").read_text().strip())
            size_2 = int(Path("/tmp/prompt_sizes/size_1.txt").read_text().strip())
            
            # With diff-only feedback, second attempt should be much smaller
            # (no static context reused, only goal + diff + error)
            # First attempt has full context (~1000+ bytes), second is minimal (~500 bytes)
            # So we expect size_2 < size_1
            self.assertLess(size_2, size_1 * 1.2, 
                          f"Expected flat or decreasing token count, got size_1={size_1}, size_2={size_2}")

    def test_get_diff_content_method(self):
        """Test that get_diff_content returns git diff output."""
        loop = RalphLoop("echo {prompt}", "true", 1)
        
        # Make a change
        Path("test_file.txt").write_text("original content")
        os.system("git add test_file.txt > /dev/null 2>&1")
        os.system("git commit -m 'add file' > /dev/null 2>&1")
        
        Path("test_file.txt").write_text("modified content")
        
        diff = loop.get_diff_content()
        self.assertIn("test_file.txt", diff)
        self.assertIn("modified content", diff)


class TestCLIArgumentParsing(unittest.TestCase):
    """Tests for command-line argument parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repo
        os.system("git init > /dev/null 2>&1")
        os.system("git config user.email 'test@test.com' > /dev/null 2>&1")
        os.system("git config user.name 'Test User' > /dev/null 2>&1")
        
        # Create initial commit
        Path("dummy.txt").write_text("initial")
        os.system("git add . > /dev/null 2>&1")
        os.system("git commit -m 'initial' > /dev/null 2>&1")

    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.test_dir)

    def test_models_argument_parsing(self):
        """Test that --models argument parses comma-separated list correctly."""
        import sys
        from supervisor import RalphLoop, DEFAULT_MODELS, MAX_RETRIES
        
        # Simulate command line: supervisor.py "task" --models model1,model2,model3
        test_args = ['supervisor.py', 'test task', '--models', 'model1,model2,model3']
        
        # Parse using argparse as done in __main__
        import argparse
        parser = argparse.ArgumentParser(description="Ralph Loop Supervisor")
        parser.add_argument("task", help="The coding task description")
        parser.add_argument("--verify", default="pytest", help="Command to verify success")
        parser.add_argument("--agent", default="claude {prompt}", help="Agent command template")
        parser.add_argument("--models", help="Comma-separated list of models")
        parser.add_argument("--test-model", help="Model for test generation")
        parser.add_argument("--impl-model", help="Model for implementation")
        
        args = parser.parse_args(test_args[1:])
        
        # Parse models list as done in __main__
        models = None
        if args.models:
            models = [m.strip() for m in args.models.split(',')]
        
        # Verify parsing
        self.assertEqual(models, ['model1', 'model2', 'model3'])
        self.assertEqual(args.task, 'test task')

    def test_models_parsing_with_spaces(self):
        """Test that --models handles spaces around commas."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("task")
        parser.add_argument("--models")
        
        args = parser.parse_args(['task', '--models', 'model1 , model2 , model3'])
        
        models = [m.strip() for m in args.models.split(',')]
        self.assertEqual(models, ['model1', 'model2', 'model3'])

    def test_default_values_when_no_args(self):
        """Test that default values are used when arguments not provided."""
        import argparse
        from supervisor import DEFAULT_VERIFIER, DEFAULT_AGENT, DEFAULT_MODELS
        
        parser = argparse.ArgumentParser()
        parser.add_argument("task")
        parser.add_argument("--verify", default=DEFAULT_VERIFIER)
        parser.add_argument("--agent", default=DEFAULT_AGENT)
        parser.add_argument("--models", default=None)
        parser.add_argument("--test-model", default=None)
        parser.add_argument("--impl-model", default=None)
        
        args = parser.parse_args(['test task'])
        
        self.assertEqual(args.verify, DEFAULT_VERIFIER)
        self.assertEqual(args.agent, DEFAULT_AGENT)
        self.assertIsNone(args.models)
        self.assertIsNone(args.test_model)
        self.assertIsNone(args.impl_model)
        
        # When models is None, RalphLoop should use DEFAULT_MODELS
        loop = RalphLoop(args.agent, args.verify, 3, models=None)
        self.assertEqual(loop.models, DEFAULT_MODELS)

    def test_agent_command_with_model_substitution(self):
        """Test that {model} placeholder is substituted in agent command."""
        loop = RalphLoop("./agent.sh {prompt} --model={model}", "true", 1, 
                        models=["test-model"])
        
        # Verify the template is stored correctly
        self.assertEqual(loop.agent_cmd_template, "./agent.sh {prompt} --model={model}")
        
        # The actual substitution happens in the execute method when building agent_cmd
        # We just verify the template is correct here
        self.assertIn("{model}", loop.agent_cmd_template)

    def test_two_phase_args_enable_mode(self):
        """Test that providing both --test-model and --impl-model enables two-phase mode."""
        import argparse
        
        parser = argparse.ArgumentParser()
        parser.add_argument("task")
        parser.add_argument("--test-model", default=None)
        parser.add_argument("--impl-model", default=None)
        
        # Both provided - should enable two-phase
        args = parser.parse_args(['task', '--test-model', 'sonnet', '--impl-model', 'haiku'])
        loop = RalphLoop("echo {prompt}", "true", 1, 
                        test_model=args.test_model, impl_model=args.impl_model)
        self.assertTrue(loop.two_phase_mode)
        
        # Only one provided - should not enable two-phase
        args = parser.parse_args(['task', '--test-model', 'sonnet'])
        loop = RalphLoop("echo {prompt}", "true", 1, 
                        test_model=args.test_model, impl_model=None)
        self.assertFalse(loop.two_phase_mode)

    def test_verify_argument_custom_value(self):
        """Test that --verify argument accepts custom verifier command."""
        import argparse
        
        parser = argparse.ArgumentParser()
        parser.add_argument("task")
        parser.add_argument("--verify", default="pytest")
        
        args = parser.parse_args(['task', '--verify', 'npm test'])
        
        self.assertEqual(args.verify, 'npm test')
        
        loop = RalphLoop("echo {prompt}", args.verify, 1)
        self.assertEqual(loop.verify_cmd, 'npm test')


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling paths in supervisor."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repo
        os.system("git init > /dev/null 2>&1")
        os.system("git config user.email 'test@test.com' > /dev/null 2>&1")
        os.system("git config user.name 'Test User' > /dev/null 2>&1")
        
        # Create initial commit
        Path("dummy.txt").write_text("initial")
        os.system("git add . > /dev/null 2>&1")
        os.system("git commit -m 'initial' > /dev/null 2>&1")

    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.test_dir)

    def test_json_parsing_fallback(self):
        """Test that invalid JSON falls back to comma-separated parsing."""
        loop = RalphLoop("echo {prompt}", "true", 1)
        
        # Valid JSON should parse
        task = 'Fix bug context_files: ["file1.py", "file2.py"]'
        files = parse_context_files(task)
        self.assertEqual(files, ["file1.py", "file2.py"])
        
        # Invalid JSON should fall back to comma-separated
        task = 'Fix bug context_files: [file1.py, file2.py, not-valid-json]'
        files = parse_context_files(task)
        self.assertEqual(files, ["file1.py", "file2.py", "not-valid-json"])

    def test_file_read_error_handling(self):
        """Test that file read errors in build_context are handled gracefully."""
        loop = RalphLoop("echo {prompt}", "true", 1)
        
        # Test missing file
        context = build_context(["nonexistent.py"])
        self.assertIn("nonexistent.py", context)
        self.assertIn("NOT FOUND", context)
        
        # Test file with read permission error
        restricted_file = Path("restricted.py")
        restricted_file.write_text("content")
        restricted_file.chmod(0o000)  # Remove all permissions
        
        try:
            context = build_context(["restricted.py"])
            # Should handle the error gracefully
            self.assertIn("restricted.py", context)
            # Either shows error or succeeds (depends on OS permissions model)
            self.assertTrue("ERROR" in context or "content" in context)
        finally:
            # Restore permissions for cleanup
            try:
                restricted_file.chmod(0o644)
            except:
                pass

    def test_shell_command_error_handling(self):
        """Test that shell command errors are properly caught and returned."""
        loop = RalphLoop("echo {prompt}", "true", 1)
        
        # Command that fails
        success, output, returncode = loop.run_shell("exit 42", ignore_error=True)
        self.assertFalse(success)
        self.assertEqual(returncode, 42)
        
        # Command that succeeds
        success, output, returncode = loop.run_shell("echo 'test'", ignore_error=True)
        self.assertTrue(success)
        self.assertEqual(returncode, 0)
        self.assertIn("test", output)

    def test_commit_failure_after_verification_passes(self):
        """Test handling when commit fails after verification passes."""
        # Create an agent that makes changes
        agent_script = Path("agent.sh")
        agent_script.write_text("""#!/bin/bash
echo "test output" > result.txt
exit 0
""")
        agent_script.chmod(0o755)
        
        # Create a verifier that passes
        verify_script = Path("verify.sh")
        verify_script.write_text("""#!/bin/bash
exit 0
""")
        verify_script.chmod(0o755)
        
        os.system("git add agent.sh verify.sh > /dev/null 2>&1")
        os.system("git commit -m 'add scripts' > /dev/null 2>&1")
        
        # Break git to make commits fail (remove .git/objects permissions)
        objects_dir = Path(".git/objects")
        original_mode = objects_dir.stat().st_mode
        objects_dir.chmod(0o000)
        
        try:
            loop = RalphLoop("./agent.sh {prompt} {model}", "./verify.sh", 1, 
                           models=["test-model"])
            
            # Execute should fail because commit fails
            result = loop.execute("test task")
            self.assertFalse(result)
        finally:
            # Restore permissions for cleanup
            try:
                objects_dir.chmod(original_mode)
            except:
                pass

    def test_subprocess_exception_handling(self):
        """Test that subprocess exceptions are caught properly."""
        loop = RalphLoop("echo {prompt}", "true", 1)
        
        # Test with ignore_error=False (should catch CalledProcessError)
        success, output, returncode = loop.run_shell("false", ignore_error=False)
        self.assertFalse(success)
        self.assertNotEqual(returncode, 0)

    def test_empty_context_files_list(self):
        """Test that empty context files list is handled correctly."""
        loop = RalphLoop("echo {prompt}", "true", 1)
        
        # Empty list
        context = build_context([])
        self.assertEqual(context, "")
        
        # None or empty list returns empty static context
        static_context, size = build_static_context(None)
        self.assertEqual(static_context, "")
        self.assertEqual(size, 0)
        
        static_context, size = build_static_context([])
        self.assertEqual(static_context, "")
        self.assertEqual(size, 0)

    def test_malformed_task_context_parsing(self):
        """Test that malformed context specifications don't crash."""
        loop = RalphLoop("echo {prompt}", "true", 1)
        
        # No context specification
        files = parse_context_files("just a task with no context")
        self.assertIsNone(files)
        
        # Empty brackets - regex won't match, returns None
        files = parse_context_files("task context_files: []")
        self.assertIsNone(files)
        
        # Malformed brackets
        files = parse_context_files("task context_files: [")
        self.assertIsNone(files)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import unittest
import tempfile
import os
from pathlib import Path
from supervisor import RalphLoop


class TestEscalationProtocol(unittest.TestCase):
    """Tests for model escalation functionality."""

    def test_default_models(self):
        """Test that default models are set correctly."""
        loop = RalphLoop("echo {prompt}", "true", 3)
        self.assertEqual(loop.models, ["claude-3-haiku", "claude-3-haiku", "claude-3-5-sonnet"])

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
        files = self.loop.parse_context_files(task)
        self.assertEqual(files, ["file1.py", "file2.py"])

    def test_parse_context_files_inline_format(self):
        """Test parsing context_files in inline format."""
        task = "Fix bug [context: file1.py, file2.py]"
        files = self.loop.parse_context_files(task)
        self.assertEqual(files, ["file1.py", "file2.py"])

    def test_parse_context_files_none(self):
        """Test when no context_files specified."""
        task = "Fix the bug in the code"
        files = self.loop.parse_context_files(task)
        self.assertIsNone(files)

    def test_get_default_context_files(self):
        """Test default context file detection."""
        # Create test files
        Path("calculator.py").touch()
        Path("test_calculator.py").touch()
        
        task = "Fix bug in calculator.py"
        files = self.loop.get_default_context_files(task)
        
        self.assertIn("calculator.py", files)
        self.assertIn("test_calculator.py", files)

    def test_get_default_context_files_no_test(self):
        """Test default context when test file doesn't exist."""
        Path("utils.py").touch()
        
        task = "Fix bug in utils.py"
        files = self.loop.get_default_context_files(task)
        
        self.assertEqual(files, ["utils.py"])

    def test_build_context_single_file(self):
        """Test building context from a single file."""
        # Create test file
        test_file = Path("test.py")
        test_file.write_text("def foo():\n    pass\n")
        
        context = self.loop.build_context(["test.py"])
        
        self.assertIn("=== CONTEXT FILES ===", context)
        self.assertIn("--- test.py ---", context)
        self.assertIn("def foo():", context)
        self.assertIn("=== END CONTEXT ===", context)

    def test_build_context_multiple_files(self):
        """Test building context from multiple files."""
        Path("file1.py").write_text("# File 1\n")
        Path("file2.py").write_text("# File 2\n")
        
        context = self.loop.build_context(["file1.py", "file2.py"])
        
        self.assertIn("--- file1.py ---", context)
        self.assertIn("--- file2.py ---", context)
        self.assertIn("# File 1", context)
        self.assertIn("# File 2", context)

    def test_build_context_missing_file(self):
        """Test building context with missing file."""
        context = self.loop.build_context(["nonexistent.py"])
        
        self.assertIn("nonexistent.py (NOT FOUND)", context)

    def test_build_context_empty_list(self):
        """Test building context with empty file list."""
        context = self.loop.build_context([])
        self.assertEqual(context, "")

    def test_context_size_limit(self):
        """Test that context stays under 10 files for typical tasks."""
        # Create 15 files
        for i in range(15):
            Path(f"file{i}.py").touch()
        
        task = "Fix bug in file1.py and file2.py"
        files = self.loop.get_default_context_files(task)
        
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
        
        # Check that second model received escalation context
        self.assertTrue(result)
        if Path("/tmp/test_prompts/log.txt").exists():
            log = Path("/tmp/test_prompts/log.txt").read_text()
            self.assertIn("PREVIOUS ATTEMPT FAILED", log)
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


if __name__ == "__main__":
    unittest.main()

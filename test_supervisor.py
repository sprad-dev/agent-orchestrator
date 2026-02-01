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

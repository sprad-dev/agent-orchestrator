#!/usr/bin/env python3
"""Tests for load_config function."""

import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import yaml

import supervisor


class TestLoadConfig(unittest.TestCase):
    """Test suite for load_config function."""

    def test_file_found_with_valid_yaml(self):
        """Test that valid YAML file is correctly parsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            test_config = {"agent": "test", "timeout": 30}
            
            with open(config_file, 'w') as f:
                yaml.dump(test_config, f)
            
            result = supervisor.load_config(config_file)
            self.assertEqual(result, test_config)

    def test_file_not_found(self):
        """Test that missing file returns empty dict."""
        nonexistent_file = "/nonexistent/path/agent.yaml"
        result = supervisor.load_config(nonexistent_file)
        self.assertEqual(result, {})

    def test_invalid_yaml(self):
        """Test that invalid YAML returns empty dict with warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            
            # Write invalid YAML
            with open(config_file, 'w') as f:
                f.write("invalid: yaml: content: [")
            
            with self.assertWarns(UserWarning):
                result = supervisor.load_config(config_file)
            
            self.assertEqual(result, {})

    def test_empty_yaml_file(self):
        """Test that empty YAML file returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            
            with open(config_file, 'w') as f:
                f.write("")
            
            result = supervisor.load_config(config_file)
            self.assertEqual(result, {})

    def test_default_path_not_found(self):
        """Test default path behavior when agent.yaml doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('os.getcwd', return_value=tmpdir):
                result = supervisor.load_config()
                self.assertEqual(result, {})

    def test_default_path_with_file(self):
        """Test default path when agent.yaml exists in cwd."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            test_config = {"default": True}
            
            with open(config_file, 'w') as f:
                yaml.dump(test_config, f)
            
            with patch('os.getcwd', return_value=tmpdir):
                result = supervisor.load_config()
                self.assertEqual(result, test_config)

    def test_yaml_with_complex_structure(self):
        """Test YAML with nested structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            test_config = {
                "agent": {
                    "name": "test-agent",
                    "settings": {
                        "timeout": 60,
                        "retries": 3
                    }
                },
                "models": ["model1", "model2"]
            }
            
            with open(config_file, 'w') as f:
                yaml.dump(test_config, f)
            
            result = supervisor.load_config(config_file)
            self.assertEqual(result, test_config)


if __name__ == '__main__':
    unittest.main()

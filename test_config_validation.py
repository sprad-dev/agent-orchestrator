#!/usr/bin/env python3
"""Tests for config validation in supervisor.py."""

import os
import tempfile
import unittest
import warnings
from unittest.mock import patch

import yaml

import supervisor


class TestValidateConfig(unittest.TestCase):
    """Test suite for validate_config function."""

    def test_empty_config_no_warnings(self):
        """Test that empty config produces no warnings."""
        warnings_list = supervisor.validate_config({})
        self.assertEqual(warnings_list, [])

    def test_valid_config_no_warnings(self):
        """Test that valid config produces no warnings."""
        config = {
            'verify_cmd': 'pytest',
            'agent_cmd': 'claude {prompt}',
            'models': ['model1', 'model2']
        }
        warnings_list = supervisor.validate_config(config)
        self.assertEqual(warnings_list, [])

    def test_agent_cmd_missing_prompt_placeholder(self):
        """Test warning when agent_cmd doesn't contain {prompt}."""
        config = {
            'agent_cmd': 'claude --model claude-4.5-sonnet'
        }
        warnings_list = supervisor.validate_config(config)
        self.assertTrue(any('{prompt}' in w for w in warnings_list))

    def test_agent_cmd_with_prompt_placeholder_no_warning(self):
        """Test that agent_cmd with {prompt} produces no warning."""
        config = {
            'agent_cmd': 'claude {prompt} --model claude-4.5-sonnet'
        }
        warnings_list = supervisor.validate_config(config)
        self.assertEqual(warnings_list, [])

    def test_agent_cmd_not_string_warning(self):
        """Test warning when agent_cmd is not a string."""
        config = {
            'agent_cmd': ['claude', '{prompt}']
        }
        warnings_list = supervisor.validate_config(config)
        self.assertTrue(any('string' in w.lower() for w in warnings_list))

    def test_verify_cmd_not_string_warning(self):
        """Test warning when verify_cmd is not a string."""
        config = {
            'verify_cmd': 123
        }
        warnings_list = supervisor.validate_config(config)
        self.assertTrue(any('string' in w.lower() for w in warnings_list))

    def test_verify_cmd_empty_string_warning(self):
        """Test warning when verify_cmd is an empty string."""
        config = {
            'verify_cmd': '   '
        }
        warnings_list = supervisor.validate_config(config)
        self.assertTrue(any('empty' in w.lower() for w in warnings_list))

    def test_models_not_list_warning(self):
        """Test warning when models is not a list."""
        config = {
            'models': 'model1,model2'
        }
        warnings_list = supervisor.validate_config(config)
        self.assertTrue(any('list' in w.lower() for w in warnings_list))

    def test_models_with_non_string_items_warning(self):
        """Test warning when models list contains non-strings."""
        config = {
            'models': ['model1', 123, 'model2']
        }
        warnings_list = supervisor.validate_config(config)
        self.assertTrue(any('string' in w.lower() for w in warnings_list))

    def test_models_valid_list_no_warning(self):
        """Test that valid models list produces no warning."""
        config = {
            'models': ['model1', 'model2', 'model3']
        }
        warnings_list = supervisor.validate_config(config)
        # Should have no warnings about models
        self.assertTrue(all('models' not in w.lower() or 'unknown' not in w.lower() 
                           for w in warnings_list))

    def test_unknown_keys_warning(self):
        """Test warning for unknown config keys."""
        config = {
            'agent_cmd': 'claude {prompt}',
            'unknown_key_1': 'value',
            'unknown_key_2': 'value'
        }
        warnings_list = supervisor.validate_config(config)
        self.assertTrue(any('unknown' in w.lower() for w in warnings_list))
        self.assertTrue(any('unknown_key' in w for w in warnings_list))

    def test_known_keys_no_unknown_warning(self):
        """Test that all known keys don't trigger unknown keys warning."""
        config = {
            'verify_cmd': 'pytest',
            'agent_cmd': 'claude {prompt}',
            'models': ['m1'],
            'test_model': 'claude-4.5-sonnet',
            'impl_model': 'claude-4.5-haiku',
            'adversary_model': 'claude-4.5-sonnet',
            'max_cost': 10.0,
            'max_tokens': 100000
        }
        warnings_list = supervisor.validate_config(config)
        # Should have no warnings at all
        self.assertEqual(warnings_list, [])

    def test_none_values_ignored(self):
        """Test that None values in config don't cause warnings."""
        config = {
            'agent_cmd': None,
            'verify_cmd': None,
            'models': None
        }
        warnings_list = supervisor.validate_config(config)
        # None values should be skipped
        self.assertEqual(warnings_list, [])

    def test_empty_list_for_models_ignored(self):
        """Test that empty models list doesn't cause warnings."""
        config = {
            'models': []
        }
        warnings_list = supervisor.validate_config(config)
        self.assertEqual(warnings_list, [])


class TestLoadConfigWithValidation(unittest.TestCase):
    """Test load_config with YAML structure validation."""

    def test_yaml_dict_returns_config(self):
        """Test that valid YAML dict is returned as config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            test_config = {'agent_cmd': 'claude {prompt}'}
            
            with open(config_file, 'w') as f:
                yaml.dump(test_config, f)
            
            result = supervisor.load_config(config_file)
            self.assertEqual(result, test_config)

    def test_yaml_list_returns_empty_dict(self):
        """Test that YAML list triggers warning and returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            
            # Write a YAML list instead of dict
            with open(config_file, 'w') as f:
                yaml.dump(['item1', 'item2'], f)
            
            with self.assertWarns(UserWarning):
                result = supervisor.load_config(config_file)
            
            self.assertEqual(result, {})

    def test_yaml_scalar_returns_empty_dict(self):
        """Test that YAML scalar triggers warning and returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            
            # Write a scalar (just a string)
            with open(config_file, 'w') as f:
                f.write("just a string")
            
            with self.assertWarns(UserWarning):
                result = supervisor.load_config(config_file)
            
            self.assertEqual(result, {})

    def test_yaml_number_returns_empty_dict(self):
        """Test that YAML number triggers warning and returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            
            # Write a number
            with open(config_file, 'w') as f:
                f.write("42")
            
            with self.assertWarns(UserWarning):
                result = supervisor.load_config(config_file)
            
            self.assertEqual(result, {})

    def test_yaml_boolean_returns_empty_dict(self):
        """Test that YAML boolean triggers warning and returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            
            # Write a boolean
            with open(config_file, 'w') as f:
                f.write("true")
            
            with self.assertWarns(UserWarning):
                result = supervisor.load_config(config_file)
            
            self.assertEqual(result, {})


class TestConfigValidationIntegration(unittest.TestCase):
    """Integration tests for load_config and validate_config."""

    def test_load_and_validate_valid_config(self):
        """Test loading and validating a valid config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            test_config = {
                'agent_cmd': 'claude {prompt}',
                'verify_cmd': 'pytest',
                'models': ['model1', 'model2']
            }
            
            with open(config_file, 'w') as f:
                yaml.dump(test_config, f)
            
            config = supervisor.load_config(config_file)
            warnings_list = supervisor.validate_config(config)
            
            self.assertEqual(config, test_config)
            self.assertEqual(warnings_list, [])

    def test_load_invalid_yaml_then_validate(self):
        """Test that loading invalid YAML returns empty dict, validate returns no warnings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            
            # Write invalid YAML
            with open(config_file, 'w') as f:
                f.write("invalid: yaml: [")
            
            with self.assertWarns(UserWarning):
                config = supervisor.load_config(config_file)
            
            self.assertEqual(config, {})
            warnings_list = supervisor.validate_config(config)
            self.assertEqual(warnings_list, [])

    def test_load_non_dict_yaml_then_validate(self):
        """Test that loading non-dict YAML returns empty dict, validate returns no warnings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            
            with open(config_file, 'w') as f:
                yaml.dump(['list', 'items'], f)
            
            with self.assertWarns(UserWarning):
                config = supervisor.load_config(config_file)
            
            self.assertEqual(config, {})
            warnings_list = supervisor.validate_config(config)
            self.assertEqual(warnings_list, [])

    def test_load_and_validate_with_warnings(self):
        """Test loading and validating a config with issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "agent.yaml")
            test_config = {
                'agent_cmd': 'claude',  # Missing {prompt}
                'unknown_key': 'value'
            }
            
            with open(config_file, 'w') as f:
                yaml.dump(test_config, f)
            
            config = supervisor.load_config(config_file)
            warnings_list = supervisor.validate_config(config)
            
            self.assertEqual(config, test_config)
            self.assertTrue(len(warnings_list) >= 2)  # Both {prompt} and unknown_key warnings
            self.assertTrue(any('{prompt}' in w for w in warnings_list))
            self.assertTrue(any('unknown' in w.lower() for w in warnings_list))


if __name__ == '__main__':
    unittest.main()

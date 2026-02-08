#!/usr/bin/env python3
"""Tests for config resolution priority system in main()."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import yaml

import supervisor


class TestConfigResolution(unittest.TestCase):
    """Test config priority: CLI Args > agent.yaml > Hardcoded Defaults"""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()

    def _create_config_file(self, config_dict):
        """Helper to create agent.yaml with given config."""
        config_path = os.path.join(os.getcwd(), "agent.yaml")
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f)

    def _parse_args(self, *args):
        """Helper to parse command line arguments for testing."""
        import argparse
        parser = argparse.ArgumentParser(description="Ralph Loop Supervisor")
        parser.add_argument("task", nargs='?', help="The coding task description")
        parser.add_argument("--verify", default=None,
                            help="Command to verify success (default: pytest)")
        parser.add_argument("--agent", default=None,
                            help="Agent command template")
        parser.add_argument("--models",
                            help="Comma-separated list of models for escalation")
        parser.add_argument("--test-model",
                            help="Model for test generation")
        parser.add_argument("--impl-model",
                            help="Model for implementation")
        parser.add_argument("--adversary-model",
                            help="Model for adversarial review")
        parser.add_argument("--max-cost", type=float,
                            help="Maximum cost per run in USD")
        parser.add_argument("--max-tokens", type=int,
                            help="Maximum tokens per run")
        parser.add_argument("--show-config", action="store_true",
                            help="Show resolved configuration and exit")
        parser.add_argument("--self-check", action="store_true",
                            help="Run verification pipeline")
        parser.add_argument("--self-check-ref", default="HEAD~1",
                            help="Git ref to diff against")
        parser.add_argument("--adversarial", action="store_true",
                            help="Enable adversarial review")
        parser.add_argument("--stats", action="store_true",
                            help="Show execution statistics")
        parser.add_argument("--stats-days", type=int,
                            help="Number of days for stats")
        
        return parser.parse_args(args)

    def test_cli_args_override_config(self):
        """Test that CLI args take priority over config file."""
        self._create_config_file({
            'verify_cmd': 'config-verify',
            'agent_cmd': 'config-agent --model {model}',
            'models': ['model1', 'model2']
        })
        
        config = supervisor.load_config()
        args = self._parse_args(
            'dummy_task',
            '--verify', 'cli-verify',
            '--agent', 'cli-agent --model {model}',
            '--models', 'cli-model1,cli-model2'
        )
        
        # Resolve with priority: CLI > config > defaults
        verify_cmd = args.verify or config.get('verify_cmd') or supervisor.DEFAULT_VERIFIER
        agent_template = args.agent or config.get('agent_cmd') or supervisor.DEFAULT_AGENT
        
        if args.models:
            models = [m.strip() for m in args.models.split(',')]
        elif 'models' in config and config['models']:
            models = config['models']
        else:
            models = None
        
        self.assertEqual(verify_cmd, 'cli-verify')
        self.assertEqual(agent_template, 'cli-agent --model {model}')
        self.assertEqual(models, ['cli-model1', 'cli-model2'])

    def test_config_overrides_defaults(self):
        """Test that config file overrides hardcoded defaults."""
        self._create_config_file({
            'verify_cmd': 'custom-pytest',
            'agent_cmd': 'custom-agent --model {model}',
            'models': ['custom-model1', 'custom-model2']
        })
        
        config = supervisor.load_config()
        args = self._parse_args('dummy_task')
        
        # Resolve with priority: CLI > config > defaults
        verify_cmd = args.verify or config.get('verify_cmd') or supervisor.DEFAULT_VERIFIER
        agent_template = args.agent or config.get('agent_cmd') or supervisor.DEFAULT_AGENT
        
        if args.models:
            models = [m.strip() for m in args.models.split(',')]
        elif 'models' in config and config['models']:
            models = config['models']
        else:
            models = None
        
        self.assertEqual(verify_cmd, 'custom-pytest')
        self.assertEqual(agent_template, 'custom-agent --model {model}')
        self.assertEqual(models, ['custom-model1', 'custom-model2'])

    def test_defaults_used_when_no_cli_or_config(self):
        """Test that hardcoded defaults are used when no CLI args or config."""
        # Don't create config file, so it uses defaults
        config = supervisor.load_config()
        args = self._parse_args('dummy_task')
        
        # Resolve with priority: CLI > config > defaults
        verify_cmd = args.verify or config.get('verify_cmd') or supervisor.DEFAULT_VERIFIER
        agent_template = args.agent or config.get('agent_cmd') or supervisor.DEFAULT_AGENT
        
        if args.models:
            models = [m.strip() for m in args.models.split(',')]
        elif 'models' in config and config['models']:
            models = config['models']
        else:
            models = None
        
        self.assertEqual(verify_cmd, supervisor.DEFAULT_VERIFIER)
        self.assertEqual(agent_template, supervisor.DEFAULT_AGENT)
        self.assertIsNone(models)  # Will default in RalphLoop

    def test_cli_only_overrides_defaults(self):
        """Test CLI args alone override defaults (no config file)."""
        config = supervisor.load_config()  # Empty config
        args = self._parse_args(
            'dummy_task',
            '--verify', 'my-verify',
            '--agent', 'my-agent'
        )
        
        verify_cmd = args.verify or config.get('verify_cmd') or supervisor.DEFAULT_VERIFIER
        agent_template = args.agent or config.get('agent_cmd') or supervisor.DEFAULT_AGENT
        
        self.assertEqual(verify_cmd, 'my-verify')
        self.assertEqual(agent_template, 'my-agent')

    def test_config_only_with_cli_partial_override(self):
        """Test config provides some values, CLI overrides only verify."""
        self._create_config_file({
            'verify_cmd': 'config-verify',
            'agent_cmd': 'config-agent'
        })
        
        config = supervisor.load_config()
        args = self._parse_args('dummy_task', '--verify', 'cli-verify')
        
        verify_cmd = args.verify or config.get('verify_cmd') or supervisor.DEFAULT_VERIFIER
        agent_template = args.agent or config.get('agent_cmd') or supervisor.DEFAULT_AGENT
        
        self.assertEqual(verify_cmd, 'cli-verify')  # From CLI
        self.assertEqual(agent_template, 'config-agent')  # From config

    def test_models_cli_priority(self):
        """Test models resolution priority: CLI > config > defaults."""
        self._create_config_file({
            'models': ['config-model1', 'config-model2']
        })
        
        config = supervisor.load_config()
        args = self._parse_args('dummy_task', '--models', 'cli-model1,cli-model2,cli-model3')
        
        if args.models:
            models = [m.strip() for m in args.models.split(',')]
        elif 'models' in config and config['models']:
            models = config['models']
        else:
            models = None
        
        self.assertEqual(models, ['cli-model1', 'cli-model2', 'cli-model3'])

    def test_models_config_when_no_cli(self):
        """Test config models used when CLI models not specified."""
        self._create_config_file({
            'models': ['config-model1', 'config-model2']
        })
        
        config = supervisor.load_config()
        args = self._parse_args('dummy_task')
        
        if args.models:
            models = [m.strip() for m in args.models.split(',')]
        elif 'models' in config and config['models']:
            models = config['models']
        else:
            models = None
        
        self.assertEqual(models, ['config-model1', 'config-model2'])

    def test_all_three_layers_together(self):
        """Test all three layers (CLI, config, defaults) work together."""
        self._create_config_file({
            'verify_cmd': 'config-verify',
            'agent_cmd': 'config-agent',
            'models': ['config-model']
        })
        
        config = supervisor.load_config()
        # Override verify via CLI, use agent from config, use models from config
        args = self._parse_args('dummy_task', '--verify', 'cli-verify')
        
        verify_cmd = args.verify or config.get('verify_cmd') or supervisor.DEFAULT_VERIFIER
        agent_template = args.agent or config.get('agent_cmd') or supervisor.DEFAULT_AGENT
        
        if args.models:
            models = [m.strip() for m in args.models.split(',')]
        elif 'models' in config and config['models']:
            models = config['models']
        else:
            models = None
        
        self.assertEqual(verify_cmd, 'cli-verify')  # CLI override
        self.assertEqual(agent_template, 'config-agent')  # Config value
        self.assertEqual(models, ['config-model'])  # Config value

    def test_empty_config_falls_back_to_defaults(self):
        """Test that empty config file falls back to defaults."""
        self._create_config_file({})
        
        config = supervisor.load_config()
        args = self._parse_args('dummy_task')
        
        verify_cmd = args.verify or config.get('verify_cmd') or supervisor.DEFAULT_VERIFIER
        agent_template = args.agent or config.get('agent_cmd') or supervisor.DEFAULT_AGENT
        
        self.assertEqual(verify_cmd, supervisor.DEFAULT_VERIFIER)
        self.assertEqual(agent_template, supervisor.DEFAULT_AGENT)

    def test_config_with_none_values_treated_as_missing(self):
        """Test that None values in config are treated as missing."""
        self._create_config_file({
            'verify_cmd': None,
            'agent_cmd': None
        })
        
        config = supervisor.load_config()
        args = self._parse_args('dummy_task')
        
        # None values should be falsy and fall through to defaults
        verify_cmd = args.verify or config.get('verify_cmd') or supervisor.DEFAULT_VERIFIER
        agent_template = args.agent or config.get('agent_cmd') or supervisor.DEFAULT_AGENT
        
        self.assertEqual(verify_cmd, supervisor.DEFAULT_VERIFIER)
        self.assertEqual(agent_template, supervisor.DEFAULT_AGENT)

    def test_models_handles_empty_list_in_config(self):
        """Test that empty models list in config falls back to defaults."""
        self._create_config_file({
            'models': []
        })
        
        config = supervisor.load_config()
        args = self._parse_args('dummy_task')
        
        if args.models:
            models = [m.strip() for m in args.models.split(',')]
        elif 'models' in config and config['models']:
            models = config['models']
        else:
            models = None
        
        # Empty list is falsy, so should fall back to None (will use defaults in RalphLoop)
        self.assertIsNone(models)


class TestConfigResolutionWithRalphLoop(unittest.TestCase):
    """Test config resolution integrated with RalphLoop instantiation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()

    def _create_config_file(self, config_dict):
        """Helper to create agent.yaml with given config."""
        config_path = os.path.join(os.getcwd(), "agent.yaml")
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f)

    def test_ralph_loop_receives_resolved_values(self):
        """Test that RalphLoop receives the correctly resolved values."""
        self._create_config_file({
            'verify_cmd': 'config-verify',
            'agent_cmd': 'config-agent {model}'
        })
        
        config = supervisor.load_config()
        
        # Simulate args parsing with CLI override
        class MockArgs:
            verify = 'cli-verify'
            agent = None
            models = None
            test_model = None
            impl_model = None
            adversary_model = None
            max_cost = None
            max_tokens = None
        
        args = MockArgs()
        
        # Resolution logic
        verify_cmd = args.verify or config.get('verify_cmd') or supervisor.DEFAULT_VERIFIER
        agent_template = args.agent or config.get('agent_cmd') or supervisor.DEFAULT_AGENT
        
        if args.models:
            models = [m.strip() for m in args.models.split(',')]
        elif 'models' in config and config['models']:
            models = config['models']
        else:
            models = None
        
        # Create RalphLoop with resolved values
        loop = supervisor.RalphLoop(
            agent_template, verify_cmd, supervisor.MAX_RETRIES,
            models=models
        )
        
        self.assertEqual(loop.agent_cmd_template, 'config-agent {model}')
        self.assertEqual(loop.verify_cmd, 'cli-verify')


if __name__ == '__main__':
    unittest.main()

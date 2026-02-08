"""Tests for L5 human approval layer and commit guard."""

import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

from src.verification.human_approval import HumanApprovalLayer
from src.guards.human_approval import HumanApprovalGuard


class TestHumanApprovalLayer:
    """Test L5 HumanApprovalLayer."""

    def test_layer_properties(self):
        """Test layer name and level."""
        layer = HumanApprovalLayer()
        assert layer.name == "HumanApproval"
        assert layer.level == 50

    def test_auto_approve(self):
        """Test auto-approve mode passes without prompting."""
        layer = HumanApprovalLayer(auto_approve=True)
        result = layer.run(modified_files=["test.py"])
        assert result.passed is True
        assert "auto-approved" in result.message

    def test_auto_approve_with_audit_log(self):
        """Test auto-approve writes audit log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "audit.jsonl")
            layer = HumanApprovalLayer(
                audit_log_path=log_path, auto_approve=True
            )
            layer.run(modified_files=["file.py"])

            with open(log_path) as f:
                entry = json.loads(f.readline())
                assert entry["approved"] is True
                assert entry["reason"] == "auto-approve"
                assert "file.py" in entry["files"]

    def test_approval_accepted(self):
        """Test that 'y' input approves."""
        layer = HumanApprovalLayer()
        with patch("builtins.input", return_value="y"):
            result = layer.run()
            assert result.passed is True
            assert "approved" in result.message

    def test_approval_rejected(self):
        """Test that empty/no input rejects."""
        layer = HumanApprovalLayer()
        with patch("builtins.input", return_value=""):
            result = layer.run()
            assert result.passed is False
            assert "rejected" in result.message

    def test_approval_rejected_on_n(self):
        """Test that 'n' input rejects."""
        layer = HumanApprovalLayer()
        with patch("builtins.input", return_value="n"):
            result = layer.run()
            assert result.passed is False

    def test_eof_rejects(self):
        """Test that EOFError (piped input) rejects."""
        layer = HumanApprovalLayer()
        with patch("builtins.input", side_effect=EOFError):
            result = layer.run()
            assert result.passed is False

    def test_keyboard_interrupt_rejects(self):
        """Test that Ctrl+C rejects."""
        layer = HumanApprovalLayer()
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result = layer.run()
            assert result.passed is False

    def test_audit_log_records_rejection(self):
        """Test audit log records rejected decisions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "audit.jsonl")
            layer = HumanApprovalLayer(audit_log_path=log_path)
            with patch("builtins.input", return_value="n"):
                layer.run(modified_files=["bad.py"])

            with open(log_path) as f:
                entry = json.loads(f.readline())
                assert entry["approved"] is False

    def test_enabled_by_default(self):
        """Test layer starts enabled."""
        layer = HumanApprovalLayer()
        assert layer.is_enabled() is True


class TestHumanApprovalGuard:
    """Test commit-time HumanApprovalGuard."""

    def test_auto_approve(self):
        """Test auto-approve mode."""
        guard = HumanApprovalGuard(auto_approve=True, audit_log_path=None)
        result = guard.check()
        assert result.passed is True

    def test_approval_accepted(self):
        """Test approved commit."""
        guard = HumanApprovalGuard(audit_log_path=None)
        with patch("builtins.input", return_value="y"):
            with patch("src.guards.human_approval.run_shell", return_value=(True, "1 file changed", 0)):
                result = guard.check()
                assert result.passed is True

    def test_approval_rejected(self):
        """Test rejected commit."""
        guard = HumanApprovalGuard(audit_log_path=None)
        with patch("builtins.input", return_value="n"):
            with patch("src.guards.human_approval.run_shell", return_value=(True, "", 0)):
                result = guard.check()
                assert result.passed is False
                assert "not approved" in result.issues[0].lower()

    def test_audit_log(self):
        """Test audit log for guard decisions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "audit.jsonl")
            guard = HumanApprovalGuard(
                auto_approve=True, audit_log_path=log_path
            )
            guard.check()

            with open(log_path) as f:
                entry = json.loads(f.readline())
                assert entry["approved"] is True
                assert "timestamp" in entry

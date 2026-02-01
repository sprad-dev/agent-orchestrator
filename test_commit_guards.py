"""Tests for commit guards secrets scanning functionality."""

import pytest
from unittest.mock import patch
from src.guards.commit import CommitGuard


class TestSecretsScanning:
    """Test secrets detection in commit diffs."""

    @pytest.fixture
    def guard(self):
        """Create a CommitGuard instance."""
        return CommitGuard()

    def test_no_secrets_in_clean_diff(self, guard):
        """Test that clean diffs pass."""
        clean_diff = """
diff --git a/file.py b/file.py
index 1234567..abcdefg 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 def hello():
+    print("Hello, world!")
     return "world"
"""
        with patch('src.guards.commit.get_diff_content', return_value=clean_diff):
            passed, issues = guard.check_secrets()
            assert passed is True
            assert len(issues) == 0

    def test_detect_aws_access_key(self, guard):
        """Test detection of AWS access keys."""
        diff_with_aws_key = """
diff --git a/config.py b/config.py
index 1234567..abcdefg 100644
--- a/config.py
+++ b/config.py
@@ -1,3 +1,4 @@
 CONFIG = {
+    "aws_key": "AKIAIOSFODNN7EXAMPLE"
 }
"""
        with patch('src.guards.commit.get_diff_content', return_value=diff_with_aws_key):
            passed, issues = guard.check_secrets()
            assert passed is False
            assert len(issues) > 0

    def test_detect_bearer_token(self, guard):
        """Test detection of Bearer tokens."""
        diff_with_bearer = """
diff --git a/auth.py b/auth.py
index 1234567..abcdefg 100644
--- a/auth.py
+++ b/auth.py
@@ -1,3 +1,4 @@
 headers = {
+    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
 }
"""
        with patch('src.guards.commit.get_diff_content', return_value=diff_with_bearer):
            passed, issues = guard.check_secrets()
            assert passed is False
            assert len(issues) > 0

    def test_detect_openai_key(self, guard):
        """Test detection of OpenAI API keys."""
        diff_with_openai = """
diff --git a/config.py b/config.py
index 1234567..abcdefg 100644
--- a/config.py
+++ b/config.py
@@ -1,3 +1,4 @@
 CONFIG = {
+    "openai_key": "sk-proj1234567890abcdefghijklmnopqrstuvwxyzABCDEF"
 }
"""
        with patch('src.guards.commit.get_diff_content', return_value=diff_with_openai):
            passed, issues = guard.check_secrets()
            assert passed is False
            assert len(issues) > 0

    def test_detect_private_keys(self, guard):
        """Test detection of private keys."""
        diff_with_rsa = """
diff --git a/keys.py b/keys.py
index 1234567..abcdefg 100644
--- a/keys.py
+++ b/keys.py
@@ -1,3 +1,5 @@
 KEYS = '''
+-----BEGIN RSA PRIVATE KEY-----
+MIIEpAIBAAKCAQEA0Z8...
 '''
"""
        with patch('src.guards.commit.get_diff_content', return_value=diff_with_rsa):
            passed, issues = guard.check_secrets()
            assert passed is False
            assert len(issues) > 0

    def test_ignore_removed_secrets(self, guard):
        """Test that secrets in removed lines (starting with -) are ignored."""
        diff_removing_secret = """
diff --git a/config.py b/config.py
index 1234567..abcdefg 100644
--- a/config.py
+++ b/config.py
@@ -1,4 +1,3 @@
 CONFIG = {
-    "aws_key": "AKIAIOSFODNN7EXAMPLE"
+    "aws_key": "use_environment_variable"
 }
"""
        with patch('src.guards.commit.get_diff_content', return_value=diff_removing_secret):
            passed, issues = guard.check_secrets()
            assert passed is True
            assert len(issues) == 0

    def test_empty_diff(self, guard):
        """Test that empty diff returns success."""
        with patch('src.guards.commit.get_diff_content', return_value=""):
            passed, issues = guard.check_secrets()
            assert passed is True
            assert len(issues) == 0

    def test_multiple_secrets_detected(self, guard):
        """Test that multiple secrets are all detected."""
        diff_with_multiple = """
diff --git a/config.py b/config.py
index 1234567..abcdefg 100644
--- a/config.py
+++ b/config.py
@@ -1,3 +1,6 @@
 CONFIG = {
+    "aws_key": "AKIAIOSFODNN7EXAMPLE",
+    "github_token": "ghp_1234567890abcdefghijklmnopqrstuvwx",
+    "openai_key": "sk-proj1234567890abcdefghijklmnopqrstuvwxyzABCDEF"
 }
"""
        with patch('src.guards.commit.get_diff_content', return_value=diff_with_multiple):
            passed, issues = guard.check_secrets()
            assert passed is False
            assert len(issues) >= 3

    def test_error_handling(self, guard):
        """Test that errors during scanning are handled gracefully."""
        with patch('src.guards.commit.get_diff_content', side_effect=Exception("Test error")):
            passed, issues = guard.check_secrets()
            assert passed is False
            assert len(issues) == 1
            assert "Error scanning for secrets" in issues[0]

    def test_check_all_integration(self, guard):
        """Test that check_all calls check_secrets."""
        diff_with_secret = """
diff --git a/config.py b/config.py
index 1234567..abcdefg 100644
--- a/config.py
+++ b/config.py
@@ -1,3 +1,4 @@
 CONFIG = {
+    "aws_key": "AKIAIOSFODNN7EXAMPLE"
 }
"""
        with patch('src.guards.commit.get_diff_content', return_value=diff_with_secret):
            passed, issues = guard.check_all()
            assert passed is False
            assert len(issues) > 0


class TestCommitGuard:
    """Test CommitGuard class."""

    def test_initialization(self):
        """Test that CommitGuard can be instantiated."""
        guard = CommitGuard()
        assert guard is not None

    def test_check_all_with_clean_repo(self):
        """Test check_all with no secrets."""
        guard = CommitGuard()
        with patch('src.guards.commit.get_diff_content', return_value=""):
            passed, issues = guard.check_all()
            assert passed is True
            assert len(issues) == 0

    def test_secret_patterns_defined(self):
        """Test that secret patterns are properly defined."""
        assert hasattr(CommitGuard, 'SECRET_PATTERNS')
        assert isinstance(CommitGuard.SECRET_PATTERNS, dict)
        assert len(CommitGuard.SECRET_PATTERNS) > 0
        
        expected_patterns = [
            'aws_access_key',
            'bearer_token',
            'openai_key',
            'private_key_rsa',
        ]
        
        for pattern in expected_patterns:
            assert pattern in CommitGuard.SECRET_PATTERNS

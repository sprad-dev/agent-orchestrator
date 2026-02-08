"""Tests for commit message validation guard."""

import pytest
from src.guards.commit_message import CommitMessageGuard, VALID_TYPES


class TestCommitMessageGuard:
    """Test CommitMessageGuard validation."""

    @pytest.fixture
    def guard(self):
        """Create a guard with conventional commit format required."""
        return CommitMessageGuard()

    def test_valid_conventional_commit(self, guard):
        """Test valid conventional commit passes."""
        result = guard.check(message="feat: add user authentication")
        assert result.passed is True
        assert result.issues == []

    def test_valid_with_scope(self, guard):
        """Test conventional commit with scope passes."""
        result = guard.check(message="fix(auth): resolve token expiration bug")
        assert result.passed is True

    def test_valid_with_body(self, guard):
        """Test conventional commit with body passes."""
        msg = "feat: add login\n\nAdded OAuth2 login flow with JWT tokens."
        result = guard.check(message=msg)
        assert result.passed is True

    def test_valid_breaking_change(self, guard):
        """Test breaking change indicator passes."""
        result = guard.check(message="feat!: redesign API endpoints")
        assert result.passed is True

    def test_all_valid_types(self, guard):
        """Test all conventional commit types pass."""
        for commit_type in VALID_TYPES:
            result = guard.check(message=f"{commit_type}: do something useful")
            assert result.passed is True, f"Type {commit_type!r} should be valid"

    def test_invalid_type(self, guard):
        """Test invalid commit type fails."""
        result = guard.check(message="yolo: ship it")
        assert result.passed is False
        assert any("Invalid commit type" in i for i in result.issues)

    def test_no_conventional_format(self, guard):
        """Test non-conventional format fails."""
        result = guard.check(message="Fixed the thing that was broken")
        assert result.passed is False
        assert any("conventional commit format" in i for i in result.issues)

    def test_subject_too_long(self, guard):
        """Test subject line over 72 chars fails."""
        long_msg = "feat: " + "x" * 70
        result = guard.check(message=long_msg)
        assert result.passed is False
        assert any("too long" in i for i in result.issues)

    def test_subject_too_short(self, guard):
        """Test subject line under 10 chars fails."""
        result = guard.check(message="fix: x")
        assert result.passed is False
        assert any("too short" in i for i in result.issues)

    def test_empty_message(self, guard):
        """Test empty message fails."""
        result = guard.check(message="")
        assert result.passed is False
        assert any("Empty" in i for i in result.issues)

    def test_missing_blank_line_before_body(self, guard):
        """Test missing blank line between subject and body fails."""
        msg = "feat: add feature\nThis is the body without blank line."
        result = guard.check(message=msg)
        assert result.passed is False
        assert any("blank line" in i for i in result.issues)

    def test_conventional_not_required(self):
        """Test non-conventional mode accepts any format."""
        guard = CommitMessageGuard(require_conventional=False)
        result = guard.check(message="Just a regular commit message here")
        assert result.passed is True

    def test_custom_max_length(self):
        """Test custom max subject length."""
        guard = CommitMessageGuard(max_subject_length=50, require_conventional=False)
        result = guard.check(message="x" * 51)
        assert result.passed is False
        assert any("too long" in i for i in result.issues)

    def test_guard_priority(self):
        """Test default priority is 15."""
        guard = CommitMessageGuard()
        assert guard.priority == 15

    def test_guard_name(self):
        """Test default name."""
        guard = CommitMessageGuard()
        assert guard.name == "commit_message"


class TestCommitMessageIntegration:
    """Test commit message guard integration with CommitGuard."""

    def test_register_in_commit_guard(self):
        """Test guard can be registered in CommitGuard registry."""
        from src.guards.commit import CommitGuard
        cg = CommitGuard()
        guard = CommitMessageGuard()
        cg.registry.register(guard)
        assert cg.registry.get_guard("commit_message") is not None

    def test_check_commit_message_method(self):
        """Test CommitGuard.check_commit_message convenience method."""
        from src.guards.commit import CommitGuard
        cg = CommitGuard()
        cg.registry.register(CommitMessageGuard())
        passed, issues = cg.check_commit_message("feat: valid message here")
        assert passed is True
        assert issues == []

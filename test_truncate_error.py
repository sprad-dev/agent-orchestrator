"""Tests for error truncation utility."""

import pytest
from src.shell import truncate_error


def test_truncate_error_short_text():
    """Text under limit is returned unchanged."""
    text = "x" * 100
    assert truncate_error(text, max_length=2000) == text


def test_truncate_error_exact_limit():
    """Text exactly at limit is returned unchanged."""
    text = "x" * 2000
    assert truncate_error(text, max_length=2000) == text


def test_truncate_error_long_text():
    """Text over limit is truncated with first/last chunks."""
    text = "A" * 5000
    result = truncate_error(text, max_length=2000)

    # Should have first 1000, middle message, last 1000
    assert result.startswith("A" * 1000)
    assert result.endswith("A" * 1000)
    assert "[truncated" in result
    assert "3000 chars]" in result  # 5000 - 2000 = 3000


def test_truncate_error_empty_string():
    """Empty string is handled correctly."""
    assert truncate_error("") == ""
    assert truncate_error(None) is None


def test_truncate_error_custom_max_length():
    """Custom max_length parameter works."""
    text = "B" * 1000
    result = truncate_error(text, max_length=100)

    # Should have first 50, middle message, last 50
    assert result.startswith("B" * 50)
    assert result.endswith("B" * 50)
    assert "[truncated 900 chars]" in result


def test_truncate_error_preserves_structure():
    """Multiline error text structure is preserved."""
    text = "Error:\n" + ("line\n" * 2000)
    result = truncate_error(text, max_length=100)

    # Should still have newlines in first/last chunks
    assert "\n" in result[:50]
    assert "\n" in result[-50:]

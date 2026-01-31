import pytest
from calculator import add

def test_add_positive_numbers():
    """Test adding two positive numbers."""
    assert add(2, 3) == 5

def test_add_negative_numbers():
    """Test adding negative numbers."""
    assert add(-1, -1) == -2

def test_add_mixed_numbers():
    """Test adding positive and negative numbers."""
    assert add(5, -3) == 2

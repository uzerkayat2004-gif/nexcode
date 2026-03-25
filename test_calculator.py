import pytest
from calculator import add

def test_add_positive():
    """Test adding two positive numbers."""
    assert add(5, 3) == 8
    assert add(10, 20) == 30

def test_add_negative():
    """Test adding negative numbers, and mixing positive and negative."""
    assert add(-5, -3) == -8
    assert add(-10, 5) == -5
    assert add(10, -5) == 5

def test_add_zero():
    """Test adding with zero."""
    assert add(5, 0) == 5
    assert add(0, 5) == 5
    assert add(0, 0) == 0

def test_add_floats():
    """Test adding floating point numbers."""
    assert add(5.5, 3.2) == pytest.approx(8.7)
    assert add(-1.5, 1.5) == 0.0

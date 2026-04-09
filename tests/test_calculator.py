import pytest
from calculator import divide

def test_divide_regular():
    """Test regular division."""
    assert divide(10, 2) == 5.0
    assert divide(15, 3) == 5.0

def test_divide_float():
    """Test floating-point division."""
    assert divide(5, 2) == 2.5
    assert divide(7.5, 2.5) == 3.0

def test_divide_negative():
    """Test division with negative numbers."""
    assert divide(-10, 2) == -5.0
    assert divide(10, -2) == -5.0
    assert divide(-10, -2) == 5.0

def test_divide_by_zero():
    """Test division by zero raises ValueError."""
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)

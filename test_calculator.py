import pytest
from calculator import multiply

def test_multiply_positive_integers():
    assert multiply(3, 4) == 12

def test_multiply_negative_integers():
    assert multiply(-3, -4) == 12

def test_multiply_mixed_signs():
    assert multiply(-3, 4) == -12
    assert multiply(3, -4) == -12

def test_multiply_by_zero():
    assert multiply(5, 0) == 0
    assert multiply(0, 5) == 0

def test_multiply_by_one():
    assert multiply(5, 1) == 5
    assert multiply(1, 5) == 5

def test_multiply_floats():
    assert multiply(2.5, 4.0) == 10.0
    assert multiply(2.5, -4.0) == -10.0
    # Floating point precision check using pytest.approx if needed
    assert multiply(0.1, 3.0) == pytest.approx(0.3)

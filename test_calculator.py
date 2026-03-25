import pytest

from calculator import subtract


def test_subtract_positive_numbers():
    assert subtract(10, 4) == 6
    assert subtract(5, 5) == 0

def test_subtract_negative_numbers():
    assert subtract(-5, -3) == -2
    assert subtract(-10, -15) == 5

def test_subtract_mixed_signs():
    assert subtract(5, -3) == 8
    assert subtract(-5, 3) == -8

def test_subtract_with_zero():
    assert subtract(5, 0) == 5
    assert subtract(0, 5) == -5
    assert subtract(0, 0) == 0

def test_subtract_floats():
    assert subtract(5.5, 2.2) == pytest.approx(3.3)
    assert subtract(0.1, 0.3) == pytest.approx(-0.2)

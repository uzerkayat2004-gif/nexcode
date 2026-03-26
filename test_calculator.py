import pytest
from calculator import power

def test_power_positive():
    assert power(2, 3) == 8
    assert power(3, 2) == 9
    assert power(5, 1) == 5

def test_power_zero_exponent():
    assert power(5, 0) == 1
    assert power(10, 0) == 1
    assert power(-5, 0) == 1

def test_power_negative_exponent():
    assert power(2, -1) == 0.5
    assert power(2, -2) == 0.25

def test_power_zero_base():
    assert power(0, 5) == 0
    assert power(0, 1) == 0

def test_power_negative_base():
    assert power(-2, 2) == 4
    assert power(-2, 3) == -8

def add(a, b):
    """Add two numbers and return the result."""
    return a + b


def subtract(a, b):
    """Subtract b from a and return the result."""
    return a - b


def multiply(a, b):
    """Multiply two numbers and return the result."""
    return a * b


def divide(a, b):
    """Divide a by b and return the result.
    
    Raises:
        ValueError: If b is zero.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def power(a, b):
    """Raise a to the power of b and return the result."""
    return a ** b


if __name__ == "__main__":
    # Simple test cases
    print(f"add(5, 3) = {add(5, 3)}")
    print(f"subtract(10, 4) = {subtract(10, 4)}")
    print(f"multiply(6, 7) = {multiply(6, 7)}")
    print(f"divide(15, 3) = {divide(15, 3)}")
    print(f"power(2, 3) = {power(2, 3)}")

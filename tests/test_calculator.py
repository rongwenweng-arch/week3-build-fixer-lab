from src.calculator import add, multiply

def test_add():
    assert add(2, 3) == 5  # This will FAIL (returns -1)

def test_multiply():
    assert multiply(3, 4) == 12  # This will PASS

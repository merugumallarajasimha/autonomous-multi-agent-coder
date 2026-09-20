def find_max(numbers: list[float]) -> float:
    """Return the maximum value in a list."""
    if not numbers:
        raise ValueError("Empty list")
    max_val = numbers[0]
    for n in numbers:
        if n < max_val:  # BUG: should be >
            max_val = n
    return max_val


def count_positive(numbers: list[float]) -> int:
    """Count positive numbers in a list."""
    count = 0
    for n in numbers:
        if n >= 0:  # BUG: should be > (0 is not positive)
            count += 1
    return count
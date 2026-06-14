"""Clean service."""

def calculate_total(items: list) -> float:
    """Calculate total from items."""
    return sum(item.price for item in items)

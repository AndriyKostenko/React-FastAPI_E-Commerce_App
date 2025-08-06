from decimal import Decimal, ROUND_HALF_UP
from schemas.product_schemas import ProductBase


def calculate_total_amount(items: list[ProductBase]) -> int:
    """Calculate total amount and return as cents (integer)"""
    # Use sum() with start=Decimal('0') to keep everything as Decimal
    total_amount = sum(
        (Decimal(str(item.price)) * Decimal(str(item.quantity)) for item in items),
        start=Decimal('0')
    )
    # Quantize to 2 decimal places
    total_amount = total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    # Convert to cents as integer
    return int(total_amount * 100)
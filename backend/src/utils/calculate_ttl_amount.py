from decimal import Decimal, ROUND_HALF_UP
from typing import List


def calculate_total_amount(items: List):
    total_amount = sum(Decimal(item.price) * Decimal(item.quantity) for item in items)
    total_amount = total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_amount *= 100  # Convert to cents
    total_amount = int(total_amount)
    return total_amount

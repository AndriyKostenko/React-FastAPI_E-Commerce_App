"""Money conversions shared by every service that moves an amount across a boundary."""

from decimal import ROUND_HALF_UP, Decimal


CENT = Decimal("0.01")


def to_cents(amount: Decimal | float | int | str) -> int:
    """Convert a major-unit amount to integer minor units, rounding half up.

    Floats go through ``str`` first so that 19.99 becomes 1999 rather than
    the 1998 its binary representation would truncate to.
    """
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(CENT)

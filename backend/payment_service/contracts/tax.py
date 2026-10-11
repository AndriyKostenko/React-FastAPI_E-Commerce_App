"""Sales-tax quote exchanged between order-service and payment-service.

order-service owns the price of an order; payment-service owns every Stripe
call. So order-service sends the priced lines here and gets back the tax to
add plus the Stripe Tax Calculation that proves it, which payment-service
later turns into the recorded tax transaction.
"""

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt


class TaxLine(BaseModel):
    """One priced order line, tax-exclusive, in minor units."""

    reference: str = Field(min_length=1, max_length=500)
    amount_cents: NonNegativeInt  # unit price x quantity
    quantity: PositiveInt


class TaxAddress(BaseModel):
    """Where the goods are shipped: the location that decides the tax."""

    country: str = Field(min_length=2, max_length=2)
    postal_code: str | None = None
    state: str | None = None
    city: str | None = None
    line1: str | None = None


class TaxCalculationRequest(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    lines: list[TaxLine] = Field(min_length=1)
    shipping_cents: NonNegativeInt = 0
    address: TaxAddress


class TaxCalculationResult(BaseModel):
    calculation_id: str
    tax_cents: NonNegativeInt  # added on top of the lines and shipping
    total_cents: NonNegativeInt

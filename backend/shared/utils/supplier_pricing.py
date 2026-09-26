"""Supplier cost to storefront retail price.

CJ reports prices in USD: ``variantSellPrice`` is what CJ charges us and
``variantSugSellPrice`` is its suggested retail. The storefront sells in CAD,
so the catalog display and the canonical order quote must both price from
this one rule, or a customer is charged a number they were never shown.
"""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from logging import Logger
from typing import Protocol, Self

from shared.utils.exchange_rates import usd_cad_rate


CENT = Decimal("0.01")


class _PricingSettings(Protocol):
    CJ_USD_TO_CAD_RATE: Decimal
    CJ_PRICE_MARKUP_MULTIPLIER: Decimal
    CJ_FX_SOURCE: str


class SupplierRetailPricing:
    """Turns a supplier's USD cost and suggested price into a CAD retail price."""

    def __init__(self, usd_to_cad_rate: Decimal, markup_multiplier: Decimal) -> None:
        if usd_to_cad_rate <= 0:
            raise ValueError("usd_to_cad_rate must be positive")
        if markup_multiplier < 1:
            raise ValueError("markup_multiplier must be at least 1")
        self.usd_to_cad_rate: Decimal = Decimal(usd_to_cad_rate)
        self.markup_multiplier: Decimal = Decimal(markup_multiplier)

    @classmethod
    def from_settings(cls, settings: _PricingSettings, usd_to_cad_rate: Decimal | None = None) -> Self:
        """``usd_to_cad_rate`` is the live rate; without one, the configured rate."""
        return cls(
            usd_to_cad_rate=usd_to_cad_rate if usd_to_cad_rate is not None else settings.CJ_USD_TO_CAD_RATE,
            markup_multiplier=settings.CJ_PRICE_MARKUP_MULTIPLIER,
        )

    @classmethod
    async def live(cls, settings: _PricingSettings, logger: Logger) -> Self:
        """Pricing at today's USD/CAD rate (see ``shared.utils.exchange_rates``)."""
        rate = await usd_cad_rate(logger).current(
            fallback=settings.CJ_USD_TO_CAD_RATE,
            source=settings.CJ_FX_SOURCE,  # type: ignore[arg-type]
        )
        return cls.from_settings(settings, rate)

    def usd_to_cad(self, amount_usd: Decimal) -> Decimal:
        """Convert a USD amount to CAD, rounded to the cent."""
        return (Decimal(amount_usd) * self.usd_to_cad_rate).quantize(
            CENT, rounding=ROUND_HALF_UP
        )

    def retail_price_cad(
        self,
        cost_usd: Decimal | None,
        suggested_usd: Decimal | None = None,
    ) -> Decimal | None:
        """Return the CAD shelf price, or ``None`` when nothing is priced.

        The price is the higher of the supplier's suggested retail and cost
        times the markup, so a missing or low suggestion can never push a sale
        below the margin floor. It is then rounded up to the next ``.99``.
        """
        cost = Decimal(cost_usd) if cost_usd is not None and cost_usd > 0 else None
        suggested = (
            Decimal(suggested_usd)
            if suggested_usd is not None and suggested_usd > 0
            else None
        )
        if cost is None and suggested is None:
            return None

        floor_usd = cost * self.markup_multiplier if cost is not None else Decimal(0)
        base_cad = max(floor_usd, suggested or Decimal(0)) * self.usd_to_cad_rate
        # Round up past the exact amount, then step back one cent: the shelf
        # price ends in .99 and never undercuts the computed price.
        return (base_cad + CENT).to_integral_value(rounding=ROUND_CEILING) - CENT

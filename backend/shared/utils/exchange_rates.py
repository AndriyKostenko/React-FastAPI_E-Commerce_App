"""The USD -> CAD rate that turns CJ's USD costs into storefront CAD prices."""

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from logging import Logger
from time import monotonic
from typing import Literal

import httpx


type FxSource = Literal["bank_of_canada", "fixed"]

BANK_OF_CANADA_USDCAD_URL = (
    "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1"
)


class UsdCadRate:
    """
    The Bank of Canada's daily USD/CAD rate, cached, with a configured fallback.

    - The rate is published once per business day, so it is cached for
      ``ttl_seconds`` and fetched at most that often per process.
    - A value outside ``bounds`` is treated as a bad answer, not a rate: a
      decimal slip must never reprice the catalogue by 10x.
    - When the feed cannot be reached, the last good rate is kept; with none
      yet, the caller's ``fallback`` (CJ_USD_TO_CAD_RATE) is used. Pricing
      never fails because the feed is down.

    Only the fetched rate is shared; the fallback and the source come from each
    caller, so two callers configured differently never see each other's.
    """

    def __init__(
        self,
        logger: Logger,
        *,
        ttl_seconds: float = 6 * 3600,
        bounds: tuple[Decimal, Decimal] = (Decimal("1.00"), Decimal("2.00")),
        timeout_seconds: float = 5.0,
        clock: Callable[[], float] = monotonic,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._logger = logger
        self._ttl = ttl_seconds
        self._low, self._high = bounds
        self._timeout = timeout_seconds
        self._clock = clock
        self._transport = transport
        self._cached: Decimal | None = None
        self._fetched_at = 0.0

    async def current(self, *, fallback: Decimal, source: FxSource = "bank_of_canada") -> Decimal:
        if source == "fixed":
            return Decimal(fallback)
        if self._cached is not None and self._clock() - self._fetched_at < self._ttl:
            return self._cached
        try:
            rate = await self._fetch()
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, InvalidOperation) as error:
            kept = self._cached if self._cached is not None else Decimal(fallback)
            self._logger.warning("USD/CAD rate unavailable (%s); using %s", error, kept)
            return kept
        self._cached, self._fetched_at = rate, self._clock()
        return rate

    async def _fetch(self) -> Decimal:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.get(BANK_OF_CANADA_USDCAD_URL)
            response.raise_for_status()
            observation = response.json()["observations"][-1]
        rate = Decimal(str(observation["FXUSDCAD"]["v"]))
        if not self._low <= rate <= self._high:
            raise ValueError(f"implausible USD/CAD rate {rate}")
        return rate


_process_rate: UsdCadRate | None = None


def usd_cad_rate(logger: Logger) -> UsdCadRate:
    """The process-wide rate, so every caller shares one fetch cache."""
    global _process_rate
    if _process_rate is None:
        _process_rate = UsdCadRate(logger)
    return _process_rate

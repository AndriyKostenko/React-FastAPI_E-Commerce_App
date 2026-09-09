"""Checkout-time shipping quotes from CJ Dropshipping (`freightCalculate`).

Checkout is latency-sensitive and CJ rate-limits per endpoint, so identical
carts to the same destination reuse a short-lived in-process quote.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from logging import Logger
from time import monotonic
from typing import Any, Iterable

from exceptions.cj_order_exceptions import CJFreightQuoteError
from schemas.dropshipping_schemas import (
    CJFreightOption,
    CJFreightQuoteItem,
    CJFreightQuoteRequest,
    CJFreightQuoteResponse,
)
from service_layer.cj_api_client import CJDropshippingAPIClient, CJDropshippingAPIError
from service_layer.product_service_client import (
    ProductNotFoundError,
    ProductServiceClient,
    ProductServiceError,
)
from shared.settings import Settings


CacheKey = tuple[str, str, tuple[tuple[str, int], ...]]


@dataclass(slots=True)
class _CachedQuote:
    options: list[CJFreightOption]
    expires_at: float


class FreightQuoteCache:
    """Bounded, monotonic-clock TTL cache for freight quotes.

    Deliberately process-local: quotes are cheap to recompute, and a shared
    cache would add a Redis round trip to the checkout critical path.
    """

    def __init__(self, ttl_seconds: float, max_entries: int) -> None:
        self.ttl_seconds: float = max(0.0, ttl_seconds)
        self.max_entries: int = max(1, max_entries)
        self._entries: dict[CacheKey, _CachedQuote] = {}

    def get(self, key: CacheKey) -> list[CJFreightOption] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= monotonic():
            self._entries.pop(key, None)
            return None
        return entry.options

    def put(self, key: CacheKey, options: list[CJFreightOption]) -> None:
        if not self.ttl_seconds:
            return
        self._evict_expired()
        if len(self._entries) >= self.max_entries:
            # Drop the entry closest to expiry; all entries share one TTL, so
            # that is also the oldest one.
            oldest = min(self._entries, key=lambda k: self._entries[k].expires_at)
            self._entries.pop(oldest, None)
        self._entries[key] = _CachedQuote(
            options=options, expires_at=monotonic() + self.ttl_seconds
        )

    def clear(self) -> None:
        self._entries.clear()

    def _evict_expired(self) -> None:
        now = monotonic()
        for key in [k for k, v in self._entries.items() if v.expires_at <= now]:
            self._entries.pop(key, None)


class CJFreightQuoteService:
    """Prices shipping for a cart against the live CJ logistics API."""

    def __init__(
        self,
        api_client: CJDropshippingAPIClient,
        product_service_client: ProductServiceClient,
        settings: Settings,
        logger: Logger | None = None,
        cache: FreightQuoteCache | None = None,
    ) -> None:
        self.api_client: CJDropshippingAPIClient = api_client
        self.product_service_client: ProductServiceClient = product_service_client
        self.settings: Settings = settings
        self.logger: Logger | None = logger
        self.cache: FreightQuoteCache = cache or FreightQuoteCache(
            ttl_seconds=settings.CJ_DROPSHIPPING_FREIGHT_CACHE_TTL_SECONDS,
            max_entries=settings.CJ_DROPSHIPPING_FREIGHT_CACHE_MAX_ENTRIES,
        )

    async def quote(self, request: CJFreightQuoteRequest) -> CJFreightQuoteResponse:
        """Return CJ shipping options for ``request``, cheapest first.

        Raises:
            CJFreightQuoteError: A line cannot be mapped to CJ, CJ is
                unreachable, or CJ offers no option for the destination.
        """
        quantity_by_vid = await self._resolve_vids(request.items)
        key = self._cache_key(request, quantity_by_vid)

        options = self.cache.get(key)
        if options is None:
            options = await self._fetch_options(request, quantity_by_vid)
            self.cache.put(key, options)

        if not options:
            raise CJFreightQuoteError(
                f"CJ has no shipping option to '{request.country_code}' for this cart"
            )
        return CJFreightQuoteResponse(
            country_code=request.country_code,
            postal_code=request.postal_code,
            options=options,
        )

    async def _resolve_vids(self, items: Iterable[CJFreightQuoteItem]) -> dict[str, int]:
        """Map local product/variant ids to CJ vids, collapsing duplicates."""
        quantity_by_vid: dict[str, int] = {}
        for item in items:
            try:
                _, vid = await self.product_service_client.resolve_cj_ids(
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                )
            except ProductNotFoundError as exc:
                raise CJFreightQuoteError(
                    f"Product/variant not found for item {item.product_id}: {exc}"
                ) from exc
            except ProductServiceError as exc:
                raise CJFreightQuoteError(
                    f"Unable to map item {item.product_id} to a CJ variant: {exc}"
                ) from exc
            quantity_by_vid[vid] = quantity_by_vid.get(vid, 0) + item.quantity
        return quantity_by_vid

    async def _fetch_options(
        self, request: CJFreightQuoteRequest, quantity_by_vid: dict[str, int]
    ) -> list[CJFreightOption]:
        payload: dict[str, Any] = {
            "startCountryCode": self.settings.CJ_DROPSHIPPING_DEFAULT_FROM_COUNTRY_CODE,
            "endCountryCode": request.country_code,
            "products": [
                {"vid": vid, "quantity": quantity}
                for vid, quantity in quantity_by_vid.items()
            ],
        }
        if request.postal_code:
            payload["zip"] = request.postal_code

        try:
            response = await self.api_client.calculate_freight(payload)
        except CJDropshippingAPIError as exc:
            raise CJFreightQuoteError(f"CJ could not price shipping: {exc}") from exc
        return self._parse_options(response)

    def _parse_options(self, response: dict[str, Any]) -> list[CJFreightOption]:
        data = response.get("data")
        if data is None:
            return []
        if not isinstance(data, list):
            raise CJFreightQuoteError("CJ freight response 'data' is not a list")

        options: list[CJFreightOption] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            option = self._parse_option(entry)
            if option is not None:
                options.append(option)
        options.sort(key=lambda option: option.price)
        return options

    def _parse_option(self, entry: dict[str, Any]) -> CJFreightOption | None:
        name = entry.get("logisticName")
        price = self._to_decimal(entry.get("logisticPrice"))
        if not name or price is None:
            if self.logger:
                self.logger.warning("Skipping unusable CJ freight option: %s", entry)
            return None
        return CJFreightOption(
            logistic_name=str(name),
            price=price,
            delivery_time=(
                str(entry["logisticAging"]) if entry.get("logisticAging") else None
            ),
            weight_grams=self._to_decimal(entry.get("logisticWeight")),
        )

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _cache_key(
        request: CJFreightQuoteRequest, quantity_by_vid: dict[str, int]
    ) -> CacheKey:
        return (
            request.country_code,
            request.postal_code or "",
            tuple(sorted(quantity_by_vid.items())),
        )

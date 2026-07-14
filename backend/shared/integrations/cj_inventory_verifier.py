from __future__ import annotations

import asyncio
from dataclasses import dataclass
from logging import Logger
from typing import Any

from shared.integrations.cj_api_client import CJDropshippingAPIClient, CJDropshippingAPIError
from shared.settings import Settings


@dataclass(frozen=True)
class StockVerificationResult:
    """Result of a live CJ Dropshipping stock verification."""

    requested: int
    available: int
    sufficient: bool
    buffered_available: int
    warehouses_checked: int


class CJDropshippingInventoryVerifier:
    """Verifies product-level inventory against the live CJ Dropshipping API."""

    def __init__(
        self,
        api_client: CJDropshippingAPIClient,
        settings: Settings,
        logger: Logger | None = None,
    ) -> None:
        self.api_client: CJDropshippingAPIClient = api_client
        self.settings: Settings = settings
        self.logger: Logger | None = logger

    async def verify_product_stock(
        self,
        pid: str,
        requested_quantity: int,
    ) -> StockVerificationResult:
        """Fetch live stock for a CJ product and compare against requested quantity.

        The buffer defined in settings is subtracted from CJ's reported total to
        provide a safety margin against concurrent sales.
        """
        last_error: Exception | None = None
        retries = max(0, self.settings.CJ_DROPSHIPPING_VERIFY_RETRIES)

        for attempt in range(retries + 1):
            try:
                raw = await self.api_client.request(
                    "GET",
                    self.api_client.build_url(
                        self.settings.CJ_DROPSHIPPING_INVENTORY_URL,
                        {"pid": pid},
                    ),
                    timeout=self.settings.CJ_DROPSHIPPING_VERIFY_TIMEOUT_SECONDS,
                )
                return self._parse_response(raw, requested_quantity)
            except CJDropshippingAPIError as exc:
                last_error = exc
                if self.logger:
                    self.logger.warning(
                        f"CJ inventory verification failed for pid={pid} "
                        f"(attempt {attempt + 1}/{retries + 1}): {exc}"
                    )
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        # All retries exhausted → treat as insufficient stock (fail-safe).
        raise CJDropshippingAPIError(
            f"CJ inventory verification failed for pid={pid} after {retries + 1} attempts: {last_error}"
        ) from last_error

    def _parse_response(
        self,
        raw: dict[str, Any],
        requested_quantity: int,
    ) -> StockVerificationResult:
        data = raw.get("data") if isinstance(raw, dict) else None
        if not isinstance(data, dict):
            raise CJDropshippingAPIError("CJ inventory response missing 'data' object")

        inventories = data.get("inventories") or []
        if not isinstance(inventories, list):
            raise CJDropshippingAPIError("CJ inventory response 'inventories' is not a list")

        total_available = sum(
            int(entry.get("totalInventoryNum", 0) or 0) for entry in inventories
        )
        buffer = max(0, self.settings.CJ_DROPSHIPPING_INVENTORY_BUFFER)
        buffered_available = max(0, total_available - buffer)

        return StockVerificationResult(
            requested=requested_quantity,
            available=total_available,
            sufficient=buffered_available >= requested_quantity,
            buffered_available=buffered_available,
            warehouses_checked=len(inventories),
        )

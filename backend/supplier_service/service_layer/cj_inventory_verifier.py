import asyncio
from dataclasses import dataclass
from logging import Logger
from typing import Any

from service_layer.cj_api_client import (
    CJDropshippingAPIClient,
    CJDropshippingAPIError,
    CJDropshippingNetworkError,
)
from service_layer.supplier_provider import WarehouseStock
from shared.contracts.shipping_region import CJ_WAREHOUSE_COUNTRY_CODE
from shared.settings import Settings


@dataclass(frozen=True)
class StockVerificationResult:
    """Result of a live CJ Dropshipping stock verification."""
    requested: int
    available: int
    sufficient: bool
    buffered_available: int
    warehouses_checked: int


def _in_our_warehouse(entry: object) -> bool:
    """Whether a CJ inventory row is for a warehouse orders ship from (US only)."""
    return (
        isinstance(entry, dict)
        and str(entry.get("countryCode") or "").strip().upper() == CJ_WAREHOUSE_COUNTRY_CODE
    )



class CJDropshippingInventoryVerifier:
    """
    Verifies exact variant inventory against the live CJ Dropshipping API.

    Only CJ's China warehouses count: orders ship from there (fromCountryCode),
    so stock sitting in China would pass the check and then fail to ship.
    """

    def __init__(self, api_client: CJDropshippingAPIClient, settings: Settings,logger: Logger | None = None) -> None:
        self.api_client: CJDropshippingAPIClient = api_client
        self.settings: Settings = settings
        self.logger: Logger | None = logger

    async def verify_product_stock(self, pid: str, requested_quantity: int) -> StockVerificationResult:
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
            except CJDropshippingNetworkError:
                # CJ unreachable: the client already retried. Propagate it as
                # such so the order is retried later, not failed and refunded.
                raise
            except CJDropshippingAPIError as exc:
                last_error = exc
                if self.logger:
                    self.logger.warning(f"CJ inventory verification failed for pid={pid} (attempt {attempt + 1}/{retries + 1}): {exc}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        # All retries exhausted → treat as insufficient stock (fail-safe).
        raise CJDropshippingAPIError(
            f"CJ inventory verification failed for pid={pid} after {retries + 1} attempts: {last_error}"
        ) from last_error

    async def verify_variant_stock(
        self, vid: str, requested_quantity: int
    ) -> StockVerificationResult:
        """Fetch live stock for the exact size/color VID being ordered."""
        last_error: Exception | None = None
        retries = max(0, self.settings.CJ_DROPSHIPPING_VERIFY_RETRIES)
        for attempt in range(retries + 1):
            try:
                raw = await self.api_client.request(
                    "GET",
                    self.api_client.build_url(
                        self.settings.CJ_DROPSHIPPING_VARIANT_INVENTORY_URL,
                        {"vid": vid},
                    ),
                    timeout=self.settings.CJ_DROPSHIPPING_VERIFY_TIMEOUT_SECONDS,
                )
                return self._parse_variant_response(raw, requested_quantity)
            except CJDropshippingNetworkError:
                # CJ unreachable: the client already retried. Propagate it as
                # such so the order is retried later, not failed and refunded.
                raise
            except CJDropshippingAPIError as exc:
                last_error = exc
                if self.logger:
                    self.logger.warning(
                        "CJ variant inventory verification failed for vid=%s "
                        "(attempt %s/%s): %s",
                        vid,
                        attempt + 1,
                        retries + 1,
                        exc,
                    )
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise CJDropshippingAPIError(
            f"CJ inventory verification failed for vid={vid} after "
            f"{retries + 1} attempts: {last_error}"
        ) from last_error

    def _parse_variant_response(
        self, raw: dict[str, Any], requested_quantity: int
    ) -> StockVerificationResult:
        data = raw.get("data") if isinstance(raw, dict) else None
        if not raw.get("result") or not isinstance(data, list):
            raise CJDropshippingAPIError(
                "CJ variant inventory response missing successful 'data' list"
            )
        ours = [entry for entry in data if _in_our_warehouse(entry)]
        total_available = sum(int(entry.get("totalInventoryNum", 0) or 0) for entry in ours)
        return self._result(total_available, requested_quantity, len(ours))

    def _parse_response(self, raw: dict[str, Any], requested_quantity: int) -> StockVerificationResult:
        data = raw.get("data") if isinstance(raw, dict) else None
        if not isinstance(data, dict):
            raise CJDropshippingAPIError("CJ inventory response missing 'data' object")

        inventories = data.get("inventories") or []
        if not isinstance(inventories, list):
            raise CJDropshippingAPIError("CJ inventory response 'inventories' is not a list")

        ours = [entry for entry in inventories if _in_our_warehouse(entry)]
        total_available = sum(int(entry.get("totalInventoryNum", 0) or 0) for entry in ours)
        return self._result(total_available, requested_quantity, len(ours))

    def _result(self, available: int, requested_quantity: int, warehouses: int) -> StockVerificationResult:
        buffer = max(0, self.settings.CJ_DROPSHIPPING_INVENTORY_BUFFER)
        buffered_available = max(0, available - buffer)
        return StockVerificationResult(
            requested=requested_quantity,
            available=available,
            sufficient=buffered_available >= requested_quantity,
            buffered_available=buffered_available,
            warehouses_checked=warehouses,
        )

    async def fetch_warehouse_stock(self, pid: str) -> WarehouseStock:
        """
        The product's US-warehouse stock, for the catalogue.

        CJ's product list reports stock summed over every warehouse, so an
        imported product would advertise units that are all in China.
        """
        raw = await self.api_client.request(
            "GET",
            self.api_client.build_url(self.settings.CJ_DROPSHIPPING_INVENTORY_URL, {"pid": pid}),
            timeout=self.settings.CJ_DROPSHIPPING_VERIFY_TIMEOUT_SECONDS,
        )
        data = raw.get("data") if isinstance(raw, dict) else None
        if not isinstance(data, dict):
            raise CJDropshippingAPIError("CJ inventory response missing 'data' object")

        total = sum(
            int(entry.get("totalInventoryNum", 0) or 0)
            for entry in data.get("inventories") or []
            if _in_our_warehouse(entry)
        )
        by_vid: dict[str, int] = {}
        for variant in data.get("variantInventories") or []:
            if not isinstance(variant, dict) or not variant.get("vid"):
                continue
            # The docs name the list "inventory"; tolerate "inventories" too.
            rows = variant.get("inventory") or variant.get("inventories") or []
            by_vid[str(variant["vid"])] = sum(
                int(row.get("totalInventory", row.get("totalInventoryNum", 0)) or 0)
                for row in rows
                if _in_our_warehouse(row)
            )
        return WarehouseStock(total=total, by_vid=by_vid)

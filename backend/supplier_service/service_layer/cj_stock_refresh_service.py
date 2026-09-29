"""
Hourly refresh of the catalogue's CJ stock from CJ's US warehouses.

The catalogue sync cannot keep stock current on its own: it lists only
products CJ reports as stocked in the US, so a product that sells out there
drops out of the listing and its catalogue stock is never touched again. This
refresh starts from what we sell instead (product-service's list of CJ
products) and asks CJ about every one of them, sold out or not.

For each product it sends product-service the sellable stock per variant (US
stock less CJ_DROPSHIPPING_INVENTORY_BUFFER), in batches through the outbox.
A product CJ could not be asked about keeps its current stock: a failed call
never zeroes a product that may well be in stock.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging import Logger
from typing import Any

from sqlalchemy import text

from models.outbox_models import OutboxEvent
from service_layer.outbox_event_service import OutboxEventService
from service_layer.product_service_client import ProductServiceClient
from service_layer.supplier_provider import SupplierProvider
from shared.contracts.events import SupplierStockUpdatedEvent
from shared.contracts.supplier import SupplierStockKey, SupplierStockLevel
from shared.database_layer.outbox_repository import OutboxRepository
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings

# pg_try_advisory_lock key: "stock" as ASCII. One refresh at a time, across
# every worker process, without a table to clean up after a crash.
_REFRESH_LOCK_KEY = 0x73746F636B
# CJ allows about one request per second per endpoint.
_CJ_CALL_SPACING_SECONDS = 1.1


@dataclass(slots=True)
class StockRefreshReport:
    products: int = 0
    refreshed: int = 0
    sold_out: int = 0
    failed: int = 0
    batches: int = 0
    skipped_already_running: bool = False
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "products": self.products,
            "refreshed": self.refreshed,
            "sold_out": self.sold_out,
            "failed": self.failed,
            "batches": self.batches,
            "skipped_already_running": self.skipped_already_running,
            "errors": self.errors[:20],
        }


class CJStockRefreshService:
    SUPPLIER_ID = "cjdropshipping"

    def __init__(
        self,
        settings: Settings,
        database: DatabaseSessionManager,
        provider: SupplierProvider,
        product_client: ProductServiceClient,
        logger: Logger,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._database = database
        self._provider = provider
        self._products = product_client
        self._logger = logger
        self._sleep = sleep
        self._now = clock or (lambda: datetime.now(timezone.utc))

    async def refresh(self) -> StockRefreshReport:
        """Refresh every CJ product we sell, unless another refresh is already running."""
        report = StockRefreshReport()
        engine = self._database.async_engine
        assert engine is not None
        # A session-level advisory lock lives on one connection, so it is held
        # on a dedicated one for the whole run and released explicitly.
        async with engine.connect() as lock_connection:
            locked = await lock_connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": _REFRESH_LOCK_KEY}
            )
            if not locked:
                report.skipped_already_running = True
                self._logger.info("CJ stock refresh skipped: the previous one is still running")
                return report
            try:
                await self._refresh_all(report)
            finally:
                await lock_connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": _REFRESH_LOCK_KEY}
                )
                await lock_connection.commit()
        self._logger.info("CJ stock refresh finished: %s", report.as_dict())
        return report

    async def _refresh_all(self, report: StockRefreshReport) -> None:
        keys = await self._products.list_stock_keys(self.SUPPLIER_ID)
        report.products = len(keys)
        batch: list[SupplierStockLevel] = []
        batch_measured_at: datetime | None = None
        for index, key in enumerate(keys):
            if index:
                await self._sleep(_CJ_CALL_SPACING_SECONDS)
            measured_at = self._now()
            level = await self._measure(key, report)
            if level is None:
                continue
            batch.append(level)
            # A batch is stamped with its earliest measurement: nothing in it
            # is claimed to be fresher than it is.
            batch_measured_at = batch_measured_at or measured_at
            if len(batch) >= self._settings.CJ_STOCK_REFRESH_BATCH_SIZE:
                await self._send(batch, batch_measured_at, report)
                batch, batch_measured_at = [], None
        if batch and batch_measured_at is not None:
            await self._send(batch, batch_measured_at, report)

    async def _measure(self, key: SupplierStockKey, report: StockRefreshReport) -> SupplierStockLevel | None:
        try:
            stock = await self._provider.get_warehouse_stock(key.supplier_pid)
        except Exception as exc:  # one product must not stop the refresh
            report.failed += 1
            report.errors.append(f"{key.supplier_pid}: {exc}")
            self._logger.warning("CJ stock for %s left unchanged: %s", key.supplier_pid, exc)
            return None
        sellable = stock.sellable(key.vids, self._settings.CJ_DROPSHIPPING_INVENTORY_BUFFER)
        report.refreshed += 1
        if not any(sellable.values()):
            report.sold_out += 1
        return SupplierStockLevel(supplier_pid=key.supplier_pid, variants=sellable)

    async def _send(self, batch: list[SupplierStockLevel], measured_at: datetime, report: StockRefreshReport) -> None:
        """One outbox event per batch, committed on its own: a later failure keeps what was sent."""
        event = SupplierStockUpdatedEvent(
            supplier_id=self.SUPPLIER_ID, measured_at=measured_at, levels=batch
        )
        async with self._database.transaction() as session:
            await OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)).add_outbox_event(
                event_type=event.event_type, payload=event
            )
        report.batches += 1

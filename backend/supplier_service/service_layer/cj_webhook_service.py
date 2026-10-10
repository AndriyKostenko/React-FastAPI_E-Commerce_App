"""
CJ's webhook pushes: verified, then STOCK turned into ``supplier.stock.updated``.

A STOCK push names variants and gives each one's stock per warehouse. Only
CJ's China warehouses count (orders ship from there), the safety buffer is
held back exactly as the hourly refresh does, and the levels go to
product-service through the outbox, in the same event the refresh sends. The
hourly refresh stays as the backstop for anything a push missed.

Every other topic is acknowledged and logged: PRODUCT/VARIANT arrive because
stock pushes need the product topic on, and are not acted on yet.

CJ wants a 200 within 3 seconds and switches a topic off after two hours
below 80% success, so a push that is genuinely CJ's is always acknowledged,
even one we cannot read; only a push that fails verification is refused.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from logging import Logger

from pydantic import ValidationError

from database_layer.cj_stock_subscription_repository import CJStockSubscriptionRepository
from schemas.cj_webhook_schemas import CJStockParams, CJStockRow, CJWebhookMessage, CJWebhookTopic
from service_layer.cj_webhook_signature import CJWebhookSignature, InvalidCJWebhookSignature
from service_layer.outbox_event_service import OutboxEventService
from service_layer.supplier_provider import WarehouseStock
from shared.contracts.events import SupplierStockUpdatedEvent
from shared.contracts.shipping_region import CJ_WAREHOUSE_COUNTRY_CODE
from shared.contracts.supplier import SupplierStockLevel
from shared.settings import Settings


@dataclass(slots=True)
class CJWebhookReceipt:
    """What one push led to, for the log and the tests."""

    message_id: str | None
    topic: str | None
    variants_applied: int = 0
    # Variants of products we do not sell, or with no China row in the push.
    variants_ignored: int = 0


def _in_china(row: CJStockRow) -> bool:
    return (row.country_code or "").strip().upper() == CJ_WAREHOUSE_COUNTRY_CODE


class CJWebhookService:
    SUPPLIER_ID = "cjdropshipping"

    def __init__(
        self,
        settings: Settings,
        signature: CJWebhookSignature,
        subscriptions: CJStockSubscriptionRepository,
        outbox: OutboxEventService,
        logger: Logger,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._signature = signature
        self._subscriptions = subscriptions
        self._outbox = outbox
        self._logger = logger
        self._now = clock or (lambda: datetime.now(timezone.utc))

    async def receive(self, body: bytes, signature: str | None) -> CJWebhookReceipt:
        """
        Handle one push. Raises ``InvalidCJWebhookSignature`` when it is not CJ's.

        The event is written through the caller's session, so it commits with
        the request, before CJ is answered.
        """
        try:
            self._signature.verify(body, signature)
        except InvalidCJWebhookSignature as exc:
            # A warning, not noise: a wrong openId in Vault refuses every
            # genuine push too, until CJ switches the topic off.
            self._logger.warning("CJ webhook push refused: %s", exc)
            raise
        try:
            message = CJWebhookMessage.model_validate_json(body)
        except ValidationError as exc:
            self._logger.warning(
                "CJ webhook push acknowledged but not read: %s error(s) in its envelope", exc.error_count()
            )
            return CJWebhookReceipt(message_id=None, topic=None)

        if message.type != CJWebhookTopic.STOCK:
            self._logger.info(
                "CJ webhook %s %s (%s) acknowledged, not acted on",
                message.type, message.message_type, message.message_id,
            )
            return CJWebhookReceipt(message_id=message.message_id, topic=message.type)
        return await self._stock(message)

    async def _stock(self, message: CJWebhookMessage) -> CJWebhookReceipt:
        receipt = CJWebhookReceipt(message_id=message.message_id, topic=message.type)
        try:
            params = CJStockParams.model_validate(message.params)
        except ValidationError as exc:
            self._logger.warning(
                "CJ STOCK push %s acknowledged but not read: %s error(s) in its params",
                message.message_id, exc.error_count(),
            )
            return receipt
        measured_at = self._now()

        # Variant -> its China stock. A variant whose rows name no China
        # warehouse says nothing about China (it is not "0 in China"), so it
        # is left for the hourly refresh rather than zeroed.
        china_stock: dict[str, int] = {}
        for vid, rows in params.root.items():
            in_china = [row for row in rows if _in_china(row)]
            if not in_china:
                receipt.variants_ignored += 1
                continue
            china_stock[vid] = sum(max(0, row.storage_num) for row in in_china)

        # Grouped per product: product-service's stock update is per product,
        # and only the variants named here change; the others keep their stock.
        owners = await self._subscriptions.pids_for_vids(china_stock)
        by_product: dict[str, dict[str, int]] = {}
        for vid, units in china_stock.items():
            pid = owners.get(vid)
            if pid is None:
                receipt.variants_ignored += 1
                continue
            by_product.setdefault(pid, {})[vid] = units

        levels = [
            SupplierStockLevel(
                supplier_pid=pid,
                variants=WarehouseStock(total=sum(units.values()), by_vid=units).sellable(
                    list(units), self._settings.CJ_DROPSHIPPING_INVENTORY_BUFFER
                ),
            )
            for pid, units in by_product.items()
        ]
        if levels:
            event = SupplierStockUpdatedEvent(
                supplier_id=self.SUPPLIER_ID, measured_at=measured_at, levels=levels
            )
            await self._outbox.add_outbox_event(event_type=event.event_type, payload=event)
            receipt.variants_applied = sum(len(level.variants) for level in levels)

        self._logger.info(
            "CJ STOCK push %s: %s variant(s) sent to product-service, %s ignored",
            message.message_id, receipt.variants_applied, receipt.variants_ignored,
        )
        return receipt

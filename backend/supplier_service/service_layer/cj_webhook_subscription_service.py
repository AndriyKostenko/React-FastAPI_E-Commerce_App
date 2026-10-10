"""
Which CJ products push their stock to us: registration and subscriptions.

CJ sends a STOCK push only for products the account subscribed, one by one
(subscribe-all was withdrawn in July 2026), at most 100 per call and up to the
account level's cap (1,000 at level 1). ``reconcile`` keeps that set equal to
what product-service sells: new products are subscribed, products no longer
sold are unsubscribed, and the variant -> product map the push handler needs
is refreshed on the way. It runs hourly and from ``dev.sh cj-webhook``.

``register`` points CJ's stock and product topics at our public URL; it is a
one-off per address (a tunnel URL changes every run), done by hand.
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging import Logger
from typing import Any

from database_layer.cj_stock_subscription_repository import CJStockSubscriptionRepository
from schemas.cj_webhook_schemas import CJWebhookSettingsRequest, CJWebhookSwitch
from service_layer.cj_api_client import CJDropshippingAPIClient, CJDropshippingWebhookNotEnabledError
from service_layer.product_service_client import ProductServiceClient
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings

# CJ allows about one request per second per account.
_CJ_CALL_SPACING_SECONDS = 1.1
# CJ's maximum per subscribe / unsubscribe call.
_CJ_SUBSCRIPTION_BATCH = 100


@dataclass(slots=True)
class SubscriptionReport:
    products: int = 0
    subscribed: int = 0
    unsubscribed: int = 0
    # Products CJ would not subscribe (it does not say why: an unknown
    # product, the account over its cap...). Retried next run. Subscribing
    # one twice is a success, so a lost table heals on the next run.
    refused: list[str] = field(default_factory=list)
    webhook_enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "products": self.products,
            "subscribed": self.subscribed,
            "unsubscribed": self.unsubscribed,
            "refused": self.refused[:20],
            "webhook_enabled": self.webhook_enabled,
        }


def _batches(pids: list[str]) -> Iterator[list[str]]:
    for start in range(0, len(pids), _CJ_SUBSCRIPTION_BATCH):
        yield pids[start:start + _CJ_SUBSCRIPTION_BATCH]


class CJWebhookSubscriptionService:
    SUPPLIER_ID = "cjdropshipping"
    WEBHOOK_ROUTE = "/cjdropshipping/webhook"

    def __init__(
        self,
        settings: Settings,
        database: DatabaseSessionManager,
        api_client: CJDropshippingAPIClient,
        product_client: ProductServiceClient,
        logger: Logger,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._database = database
        self._cj = api_client
        self._products = product_client
        self._logger = logger
        self._sleep = sleep
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._calls = 0

    def callback_url(self, public_base_url: str) -> str:
        """Where CJ pushes: the gateway's public address plus the webhook route."""
        api = self._settings.API_GATEWAY_SERVICE_URL_API_VERSION.rstrip("/")
        return f"{public_base_url.rstrip('/')}{api}{self.WEBHOOK_ROUTE}"

    async def register(self, public_base_url: str, switch: CJWebhookSwitch) -> str:
        """Point CJ's stock and product pushes at us (ENABLE) or stop them (CANCEL)."""
        url = self.callback_url(public_base_url)
        await self._call()
        await self._cj.set_webhooks(CJWebhookSettingsRequest.stock_only(url, switch))
        self._logger.info("CJ webhooks %s for %s", "enabled" if switch == "ENABLE" else "cancelled", url)
        return url

    async def reconcile(self) -> SubscriptionReport:
        report = SubscriptionReport()
        keys = await self._products.list_stock_keys(self.SUPPLIER_ID)
        report.products = len(keys)
        async with self._database.transaction() as session:
            repository = CJStockSubscriptionRepository(session)
            await repository.record_catalogue(keys)
            to_subscribe = await repository.list_unsubscribed_pids()
            no_longer_sold = await repository.list_not_in([key.supplier_pid for key in keys])

        # CJ is called with no transaction open; each outcome is recorded in
        # a short one of its own, so a failure part-way keeps what was done.
        never_subscribed = [row.pid for row in no_longer_sold if row.subscribed_at is None]
        await self._forget(never_subscribed)
        try:
            for batch in _batches(to_subscribe):
                await self._call()
                result = await self._cj.subscribe_products(batch)
                await self._mark_subscribed(result.success_product_ids)
                report.subscribed += len(result.success_product_ids)
                report.refused.extend(result.fail_product_ids)
            for batch in _batches([row.pid for row in no_longer_sold if row.subscribed_at is not None]):
                await self._call()
                await self._cj.unsubscribe_products(batch)
                await self._forget(batch)
                report.unsubscribed += len(batch)
        except CJDropshippingWebhookNotEnabledError:
            report.webhook_enabled = False
            self._logger.warning(
                "CJ's product webhook is off, so no product can be subscribed to stock pushes. "
                "Register the public URL: ./local/dev.sh cj-webhook enable <public url>"
            )
        if report.refused:
            self._logger.warning("CJ refused to subscribe %s product(s): %s", len(report.refused), report.refused[:20])
        self._logger.info("CJ stock subscriptions reconciled: %s", report.as_dict())
        return report

    async def _call(self) -> None:
        """Space CJ calls out: CJ answers back-to-back ones with a 429."""
        if self._calls:
            await self._sleep(_CJ_CALL_SPACING_SECONDS)
        self._calls += 1

    async def _mark_subscribed(self, pids: list[str]) -> None:
        async with self._database.transaction() as session:
            await CJStockSubscriptionRepository(session).mark_subscribed(pids, self._now())

    async def _forget(self, pids: list[str]) -> None:
        async with self._database.transaction() as session:
            await CJStockSubscriptionRepository(session).remove(pids)

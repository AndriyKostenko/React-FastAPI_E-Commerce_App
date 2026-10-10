"""
Keeping CJ's stock-push subscriptions equal to what we sell, on real Postgres.

CJ is a stand-in that records each call; product-service answers with a
fixed list. The recorded subscriptions and the variant map are the real tables.
"""

from collections.abc import AsyncGenerator
from logging import getLogger
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from models.base import Base
from models.cj_stock_subscription_models import CJStockSubscription, CJStockSubscriptionVariant
from schemas.cj_webhook_schemas import CJProductSubscriptionResult
from service_layer.cj_api_client import CJDropshippingWebhookNotEnabledError
from service_layer.cj_webhook_subscription_service import CJWebhookSubscriptionService
from shared.contracts.supplier import SupplierStockKey
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.settings import get_settings

pytestmark = pytest.mark.asyncio(loop_scope="session")


class RecordingCJ:
    """CJ's subscription endpoints: accepts all but ``refuse``, or answers that the webhook is off."""

    def __init__(self, refuse: frozenset[str] = frozenset(), webhook_off: bool = False) -> None:
        self.refuse = refuse
        self.webhook_off = webhook_off
        self.subscribe_calls: list[list[str]] = []
        self.unsubscribe_calls: list[list[str]] = []

    async def subscribe_products(self, pids: list[str]) -> CJProductSubscriptionResult:
        if self.webhook_off:
            raise CJDropshippingWebhookNotEnabledError("CJ API request failed (1606010): Product webhook is not enabled")
        self.subscribe_calls.append(list(pids))
        return CJProductSubscriptionResult(
            success_product_ids=[pid for pid in pids if pid not in self.refuse],
            fail_product_ids=[pid for pid in pids if pid in self.refuse],
        )

    async def unsubscribe_products(self, pids: list[str]) -> dict[str, bool]:
        self.unsubscribe_calls.append(list(pids))
        return {"result": True}


@pytest.fixture
async def db() -> AsyncGenerator[TestDatabaseSessionManager, None]:
    manager = TestDatabaseSessionManager(
        database_url=get_settings().SUPPLIER_SERVICE_TEST_DATABASE_URL, logger=getLogger("test")
    )
    await manager.init_db(Base.metadata)
    yield manager
    await manager.truncate_all_tables(Base.metadata)
    await manager.close()


def _service(db, cj: RecordingCJ, *keys: SupplierStockKey, sleep: AsyncMock | None = None) -> CJWebhookSubscriptionService:
    return CJWebhookSubscriptionService(
        settings=SimpleNamespace(API_GATEWAY_SERVICE_URL_API_VERSION="/api/v1"),
        database=db,
        api_client=cj,
        product_client=SimpleNamespace(list_stock_keys=AsyncMock(return_value=list(keys))),
        logger=getLogger("test"),
        sleep=sleep or AsyncMock(),
    )


async def _subscriptions(db) -> dict[str, bool]:
    async with db.transaction() as session:
        rows = (await session.execute(select(CJStockSubscription))).scalars().all()
    return {row.pid: row.subscribed_at is not None for row in rows}


async def _variant_map(db) -> dict[str, str]:
    async with db.transaction() as session:
        rows = (await session.execute(select(CJStockSubscriptionVariant))).scalars().all()
    return {row.vid: row.pid for row in rows}


async def test_products_we_sell_are_subscribed_and_their_variants_mapped(db) -> None:
    cj = RecordingCJ()
    report = await _service(
        db, cj,
        SupplierStockKey(supplier_pid="P1", vids=["V1", "V2"]),
        SupplierStockKey(supplier_pid="P2", vids=["V3"]),
    ).reconcile()

    assert cj.subscribe_calls == [["P1", "P2"]]
    assert report.subscribed == 2 and report.webhook_enabled
    assert await _subscriptions(db) == {"P1": True, "P2": True}
    assert await _variant_map(db) == {"V1": "P1", "V2": "P1", "V3": "P2"}

    # Nothing new next hour: CJ is not called at all.
    again = RecordingCJ()
    await _service(
        db, again,
        SupplierStockKey(supplier_pid="P1", vids=["V1", "V2"]),
        SupplierStockKey(supplier_pid="P2", vids=["V3"]),
    ).reconcile()
    assert again.subscribe_calls == [] and again.unsubscribe_calls == []


async def test_a_product_no_longer_sold_is_unsubscribed_and_forgotten(db) -> None:
    await _service(
        db, RecordingCJ(),
        SupplierStockKey(supplier_pid="P1", vids=["V1", "V2"]),
        SupplierStockKey(supplier_pid="P2", vids=["V3"]),
    ).reconcile()

    cj = RecordingCJ()
    # P2 is gone; P1 dropped V2 and gained V4.
    report = await _service(db, cj, SupplierStockKey(supplier_pid="P1", vids=["V1", "V4"])).reconcile()

    assert cj.unsubscribe_calls == [["P2"]]
    assert cj.subscribe_calls == []
    assert report.unsubscribed == 1
    assert await _subscriptions(db) == {"P1": True}
    assert await _variant_map(db) == {"V1": "P1", "V4": "P1"}


async def test_a_product_cj_refuses_stays_unsubscribed_and_is_tried_next_run(db) -> None:
    keys = (SupplierStockKey(supplier_pid="P1", vids=["V1"]), SupplierStockKey(supplier_pid="P2", vids=["V2"]))
    report = await _service(db, RecordingCJ(refuse=frozenset({"P2"})), *keys).reconcile()

    assert report.refused == ["P2"]
    assert await _subscriptions(db) == {"P1": True, "P2": False}

    cj = RecordingCJ()
    await _service(db, cj, *keys).reconcile()
    assert cj.subscribe_calls == [["P2"]]
    assert await _subscriptions(db) == {"P1": True, "P2": True}


async def test_with_the_webhook_off_nothing_is_marked_subscribed(db) -> None:
    report = await _service(
        db, RecordingCJ(webhook_off=True), SupplierStockKey(supplier_pid="P1", vids=["V1"])
    ).reconcile()

    assert report.webhook_enabled is False
    assert await _subscriptions(db) == {"P1": False}
    # The map is kept anyway, ready for when the webhook is registered.
    assert await _variant_map(db) == {"V1": "P1"}

    # A product dropped before it was ever subscribed needs no CJ call.
    cj = RecordingCJ(webhook_off=True)
    await _service(db, cj).reconcile()
    assert cj.unsubscribe_calls == []
    assert await _subscriptions(db) == {}


async def test_subscriptions_go_in_batches_of_100_spaced_for_cjs_rate_limit(db) -> None:
    keys = [SupplierStockKey(supplier_pid=f"P{index:03}", vids=[f"V{index:03}"]) for index in range(150)]
    cj, sleep = RecordingCJ(), AsyncMock()

    report = await _service(db, cj, *keys, sleep=sleep).reconcile()

    assert [len(call) for call in cj.subscribe_calls] == [100, 50]
    assert report.subscribed == 150
    # One pause between the two CJ calls, none before the first.
    sleep.assert_awaited_once()


async def test_cj_is_told_to_push_to_the_gateways_webhook_route() -> None:
    service = _service(None, RecordingCJ())
    assert service.callback_url("https://abc.trycloudflare.com/") == (
        "https://abc.trycloudflare.com/api/v1/cjdropshipping/webhook"
    )

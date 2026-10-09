"""
CJ's webhook pushes through the real route, signature and database.

The push is signed the way CJ signs it (HMAC-SHA256 over the exact bytes,
keyed by the openId), the variant -> product map and the outbox are real
Postgres. Only the app's resource wiring is replaced, by a service bound to
the test database.
"""

import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from logging import getLogger
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from database_layer.cj_stock_subscription_repository import CJStockSubscriptionRepository
from dependencies.dependencies import get_cj_webhook_service
from models.base import Base
from models.outbox_models import OutboxEvent
from routes.supplier_routes import supplier_routes
from service_layer.cj_webhook_service import CJWebhookService
from service_layer.cj_webhook_signature import CJWebhookSignature
from service_layer.outbox_event_service import OutboxEventService
from shared.contracts.supplier import SupplierStockKey
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import SupplierEvents
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.settings import get_settings

pytestmark = pytest.mark.asyncio(loop_scope="session")

OPEN_ID = "1234567890123"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
WEBHOOK = "/api/v1/cjdropshipping/webhook"


@pytest.fixture
async def db() -> AsyncGenerator[TestDatabaseSessionManager, None]:
    manager = TestDatabaseSessionManager(
        database_url=get_settings().SUPPLIER_SERVICE_TEST_DATABASE_URL, logger=getLogger("test")
    )
    await manager.init_db(Base.metadata)
    yield manager
    await manager.truncate_all_tables(Base.metadata)
    await manager.close()


async def _sell(db: TestDatabaseSessionManager, *keys: SupplierStockKey) -> None:
    async with db.transaction() as session:
        await CJStockSubscriptionRepository(session).record_catalogue(list(keys))


def _client(db: TestDatabaseSessionManager, buffer: int = 0) -> AsyncClient:
    app = FastAPI()
    app.include_router(supplier_routes, prefix="/api/v1")

    async def service() -> AsyncGenerator[CJWebhookService, None]:
        async with db.transaction() as session:
            yield CJWebhookService(
                settings=SimpleNamespace(CJ_DROPSHIPPING_INVENTORY_BUFFER=buffer),
                signature=CJWebhookSignature(OPEN_ID),
                subscriptions=CJStockSubscriptionRepository(session),
                outbox=OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)),
                logger=getLogger("test"),
                clock=lambda: NOW,
            )

    app.dependency_overrides[get_cj_webhook_service] = service
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _cj_body(message: dict[str, object]) -> bytes:
    # CJ serialises with fastjson: keys sorted, no spaces.
    return json.dumps(message, sort_keys=True, separators=(",", ":")).encode()


async def _push(client: AsyncClient, body: bytes, open_id: str = OPEN_ID) -> int:
    response = await client.post(
        WEBHOOK, content=body,
        headers={"content-type": "application/json", "sign": CJWebhookSignature(open_id).sign(body)},
    )
    return response.status_code


def _row(vid: str, country: str, units: int, area: str = "1") -> dict[str, object]:
    return {"vid": vid, "areaId": area, "areaEn": f"{country} Warehouse", "countryCode": country, "storageNum": units}


async def _outbox(db: TestDatabaseSessionManager) -> list[OutboxEvent]:
    async with db.transaction() as session:
        return list((await session.execute(select(OutboxEvent))).scalars().all())


async def test_a_stock_push_sends_china_stock_less_the_buffer_per_product(db) -> None:
    await _sell(
        db,
        SupplierStockKey(supplier_pid="P1", vids=["V1", "V2", "V3"]),
        SupplierStockKey(supplier_pid="P2", vids=["V4"]),
    )
    body = _cj_body({
        "messageId": "m-1",
        "type": "STOCK",
        "messageType": "UPDATE",
        "params": {
            # Two China areas count together; the US row does not count at all.
            "V1": [_row("V1", "CN", 10), _row("V1", "CN", 5, area="7"), _row("V1", "US", 99, area="2")],
            "V2": [_row("V2", "CN", 1)],
            "V4": [_row("V4", "CN", 0)],
            # Only a US row: says nothing about China, so V3 is left alone.
            "V3": [_row("V3", "US", 40, area="2")],
            # A variant of a product we do not sell.
            "V9": [_row("V9", "CN", 8)],
        },
    })

    async with _client(db, buffer=2) as client:
        assert await _push(client, body) == 200

    [event] = await _outbox(db)
    assert event.event_type == SupplierEvents.SUPPLIER_STOCK_UPDATED
    assert event.payload["supplier_id"] == "cjdropshipping"
    assert datetime.fromisoformat(event.payload["measured_at"]) == NOW
    levels = {level["supplier_pid"]: level["variants"] for level in event.payload["levels"]}
    assert levels == {"P1": {"V1": 13, "V2": 0}, "P2": {"V4": 0}}


async def test_a_push_that_is_not_signed_by_our_open_id_is_refused(db) -> None:
    await _sell(db, SupplierStockKey(supplier_pid="P1", vids=["V1"]))
    body = _cj_body({"messageId": "m-2", "type": "STOCK", "params": {"V1": [_row("V1", "CN", 0)]}})

    async with _client(db) as client:
        assert await _push(client, body, open_id="999") == 401
        unsigned = await client.post(WEBHOOK, content=body, headers={"content-type": "application/json"})
        assert unsigned.status_code == 401

    assert await _outbox(db) == []


async def test_product_pushes_are_acknowledged_and_change_nothing(db) -> None:
    await _sell(db, SupplierStockKey(supplier_pid="P1", vids=["V1"]))
    body = _cj_body({
        "messageId": "m-3", "type": "VARIANT", "messageType": "UPDATE",
        "params": {"vid": "V1", "variantStatus": 0, "fields": ["variantStatus"]},
    })

    async with _client(db) as client:
        assert await _push(client, body) == 200

    assert await _outbox(db) == []


async def test_a_genuine_push_we_cannot_read_is_still_acknowledged(db) -> None:
    # CJ switches a topic off after two hours below 80% success, so a push
    # that is CJ's must never be bounced, even one in a shape we do not know.
    async with _client(db) as client:
        assert await _push(client, b"not json at all") == 200
        assert await _push(client, _cj_body({"messageId": "m-4", "type": "STOCK", "params": ["unexpected"]})) == 200

    assert await _outbox(db) == []


async def test_a_push_about_variants_we_do_not_sell_writes_nothing(db) -> None:
    body = _cj_body({"messageId": "m-5", "type": "STOCK", "params": {"V9": [_row("V9", "CN", 3)]}})

    async with _client(db) as client:
        assert await _push(client, body) == 200

    assert await _outbox(db) == []

"""
GET /orders/{id}/details: the customer's order page, against a real database.

Covers who may read it, and that each fulfillment channel's "shipped" step
leaves the parcel on the line it moved: the in-house queue (operator enters
the tracking number), CJ (cj.order.shipped) and the local warehouse
(shipment.shipped).
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from contracts.event_enums import OrderEvents, ShippingEvents
from contracts.events import CJOrderShippedEvent, ShipmentShippedEvent
from enums.status_enums import LineFulfillmentStatus
from events_consumer.order_event_consumer import OrderEventConsumer
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.order_fulfillment_models import OrderLineFulfillment
from models.order_item_models import OrderItem
from tests.conftest import SIGNING_KEYS
from tests.constants import TEST_API, TEST_PRODUCT_ID, TEST_USER_ID
from tests.integration_tests.test_production_routes import (  # noqa: F401 (queued_job is a fixture)
    PRODUCTION_API,
    _catalog_line,
    _confirm_payment,
    _custom_order_payload,
    _signed_asset,
    queued_job,
)

OWNER = SIGNING_KEYS.caller_auth(user_id=TEST_USER_ID)
STRANGER = SIGNING_KEYS.caller_auth(user_id=uuid4())
ANONYMOUS = httpx.Auth()


def _details(order_id: str) -> str:
    return f"{TEST_API}/orders/{order_id}/details"


def _consumer(db: TestDatabaseSessionManager) -> OrderEventConsumer:
    idempotency = MagicMock(
        try_claim_event=AsyncMock(return_value=True),
        mark_event_as_processed=AsyncMock(),
        release_claim=AsyncMock(),
    )
    return OrderEventConsumer(
        logger=MagicMock(), database=db, idempotency_service=idempotency, event_publisher=MagicMock()
    )


async def _confirmed_catalog_order(client: AsyncClient, db: TestDatabaseSessionManager) -> dict:
    payload = _custom_order_payload(_signed_asset(), products=[_catalog_line(TEST_PRODUCT_ID)])
    create = await client.post(f"{TEST_API}/orders", json=payload)
    assert create.status_code == 201, create.text
    order = create.json()
    await _confirm_payment(db, UUID(order["id"]), Decimal(str(order["amount"])), order["payment_intent_id"])
    return order


async def _set_line_type(db: TestDatabaseSessionManager, order_id: str, fulfillment_type: str) -> None:
    """Make the order's line a CJ one, as a cart line priced from CJ would be."""
    async with db.transaction() as session:
        lines = await session.execute(
            select(OrderLineFulfillment)
            .join(OrderItem, OrderItem.id == OrderLineFulfillment.order_item_id)
            .where(OrderItem.order_id == UUID(order_id))
        )
        for line in lines.scalars():
            line.fulfillment_type = fulfillment_type


class TestAccess:
    async def test_owner_reads_lines_and_address(self, integration_client: AsyncClient, queued_job: dict):
        order = queued_job["order"]
        response = await integration_client.get(_details(order["id"]), auth=OWNER)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["id"] == order["id"]
        assert body["address"]["street"] == "12 Workshop Lane"
        assert body["address"]["province"] == "AB"
        assert len(body["lines"]) == 1
        line = body["lines"][0]
        assert line["fulfillment_type"] == "custom"
        assert line["status"] == LineFulfillmentStatus.QUEUED
        assert line["quantity"] == 1
        assert line["parcel"] is None

    @pytest.mark.parametrize(("caller", "status"), [(STRANGER, 403), (ANONYMOUS, 401)])
    async def test_nobody_else_reads_it(
        self, integration_client: AsyncClient, queued_job: dict, caller: httpx.Auth, status: int
    ):
        response = await integration_client.get(_details(queued_job["order"]["id"]), auth=caller)
        assert response.status_code == status

    async def test_unknown_order_is_404(self, integration_client: AsyncClient):
        response = await integration_client.get(_details(str(uuid4())))
        assert response.status_code == 404


class TestParcelTracking:
    async def test_in_house_dispatch_puts_the_parcel_on_the_line(
        self, integration_client: AsyncClient, queued_job: dict
    ):
        job_id = queued_job["job"]["id"]
        assert (await integration_client.post(f"{PRODUCTION_API}/{job_id}/start", json={})).status_code == 200
        assert (await integration_client.post(f"{PRODUCTION_API}/{job_id}/printed", json={})).status_code == 200
        shipped = await integration_client.post(
            f"{PRODUCTION_API}/{job_id}/ship",
            json={
                "tracking_number": "CP123456789CA",
                "carrier": "Canada Post",
                "tracking_url": "https://www.canadapost-postescanada.ca/track-reperage/en#/details/CP123456789CA",
            },
        )
        assert shipped.status_code == 200, shipped.text

        line = (await integration_client.get(_details(queued_job["order"]["id"]), auth=OWNER)).json()["lines"][0]
        assert line["status"] == LineFulfillmentStatus.SHIPPED
        assert line["parcel"]["tracking_number"] == "CP123456789CA"
        assert line["parcel"]["carrier"] == "Canada Post"
        assert line["parcel"]["tracking_url"].endswith("CP123456789CA")
        assert line["parcel"]["shipped_at"] is not None

    async def test_cj_shipped_event_puts_the_parcel_on_cj_lines(
        self, integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
    ):
        order = await _confirmed_catalog_order(integration_client, test_database_session_manager)
        await _set_line_type(test_database_session_manager, order["id"], "cj")

        event = CJOrderShippedEvent(
            event_type=OrderEvents.CJ_ORDER_SHIPPED,
            order_id=order["id"],
            user_id=order["user_id"],
            user_email=order["user_email"],
            cj_order_number="CJ-1001",
            tracking_number="YT2412345678901234",
            logistic_name="YunExpress",
        ).model_dump(mode="json")
        await _consumer(test_database_session_manager).handle_cj_order_event(event)

        line = (await integration_client.get(_details(order["id"]), auth=OWNER)).json()["lines"][0]
        assert line["status"] == LineFulfillmentStatus.SHIPPED
        assert line["parcel"]["tracking_number"] == "YT2412345678901234"
        # CJ's logistic name stands in for the carrier.
        assert line["parcel"]["carrier"] == "YunExpress"

    async def test_warehouse_shipment_puts_the_parcel_on_catalog_lines(
        self, integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
    ):
        order = await _confirmed_catalog_order(integration_client, test_database_session_manager)

        event = ShipmentShippedEvent(
            event_type=ShippingEvents.SHIPMENT_SHIPPED,
            shipment_id=uuid4(),
            order_id=order["id"],
            user_id=order["user_id"],
            user_email=order["user_email"],
            tracking_number="WH-0001",
            shipped_at="2026-10-15T12:00:00+00:00",
        ).model_dump(mode="json")
        await _consumer(test_database_session_manager).handle_shipping_event(event)

        line = (await integration_client.get(_details(order["id"]), auth=OWNER)).json()["lines"][0]
        assert line["status"] == LineFulfillmentStatus.SHIPPED
        assert line["parcel"]["tracking_number"] == "WH-0001"
        assert line["parcel"]["shipped_at"].startswith("2026-10-15T12:00:00")

"""End-to-end checks on how CJ lifecycle events are created and dispatched.

These guard the seam that unit tests on either side cannot see: an outbox row
is written by one process and read by another, so a payload that cannot be
rebuilt, or an event type the relay cannot route, only fails in production.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from event_publisher.supplier_event_publisher import SupplierEventPublisher
from service_layer.outbox_poller_service import build_outbox_relay
from shared.contracts.events import (
    CJOrderCreatedEvent,
    CJOrderDeliveredEvent,
    CJOrderFailedEvent,
    CJOrderPaidEvent,
    CJOrderShippedEvent,
)
from shared.enums.event_enums import OrderEvents, SupplierEvents
from shared.settings import get_settings


TEST_ORDER_ID = uuid4()
TEST_USER_ID = uuid4()

# Every event type supplier_service writes to its outbox, with a payload that
# is valid for that type.
OUTBOX_EVENTS = {
    OrderEvents.CJ_ORDER_CREATED: CJOrderCreatedEvent(
        service="supplier-service",
        order_id=TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        user_email="buyer@example.com",
        cj_order_number="CJ-1",
    ),
    OrderEvents.CJ_ORDER_FAILED: CJOrderFailedEvent(
        service="supplier-service",
        order_id=TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        user_email="buyer@example.com",
        reason="Insufficient live CJ stock",
    ),
    OrderEvents.CJ_ORDER_PAID: CJOrderPaidEvent(
        order_id=TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        user_email="buyer@example.com",
        cj_order_number="CJ-1",
        amount_usd="12.34",
    ),
    OrderEvents.CJ_ORDER_SHIPPED: CJOrderShippedEvent(
        service="supplier-service",
        order_id=TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        user_email="buyer@example.com",
        cj_order_number="CJ-1",
        tracking_number="CJP123456789CN",
        logistic_name="CJPacket Ordinary",
        tracking_url="https://cjpacket.com/track?trackNumber=CJP123456789CN",
    ),
    OrderEvents.CJ_ORDER_DELIVERED: CJOrderDeliveredEvent(
        service="supplier-service",
        order_id=TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        user_email="buyer@example.com",
        cj_order_number="CJ-1",
        tracking_number="CJP123456789CN",
    ),
}


def _make_publisher() -> SupplierEventPublisher:
    publisher = SupplierEventPublisher(
        broker=MagicMock(),
        supplier_exchange=MagicMock(name="supplier.events.exchange"),
        order_exchange=MagicMock(name="order.events.exchange"),
        inventory_exchange=MagicMock(name="inventory.events.exchange"),
        logger=MagicMock(),
        settings=get_settings(),
    )
    publisher.publish_an_event = AsyncMock()
    return publisher


def _make_router(publisher: SupplierEventPublisher):
    resources = MagicMock()
    resources.publisher = publisher
    resources.settings = get_settings()
    return build_outbox_relay(resources).event_router


class TestOutboxRoundTrip:
    @pytest.mark.parametrize("event_type", list(OUTBOX_EVENTS))
    async def test_stored_payload_rebuilds_and_publishes(self, event_type) -> None:
        """A JSON-serialized outbox row must rebuild into its event and ship."""
        publisher = _make_publisher()
        # This is exactly what OutboxEventService persists.
        stored_payload = OUTBOX_EVENTS[event_type].model_dump(mode="json")

        await _make_router(publisher)(event_type, stored_payload)

        publisher.publish_an_event.assert_awaited_once()
        kwargs = publisher.publish_an_event.await_args.kwargs
        assert kwargs["routing_key"] == event_type
        assert kwargs["exchange"] is publisher.order_exchange
        assert kwargs["event"].event_type == event_type
        assert kwargs["event"].order_id == TEST_ORDER_ID
        assert kwargs["event"].event_id == OUTBOX_EVENTS[event_type].event_id

    async def test_supplier_products_fetched_goes_to_the_supplier_exchange(self) -> None:
        publisher = _make_publisher()
        payload = {
            "service": "supplier-service",
            "supplier_id": "cjdropshipping",
            "fetch_id": str(uuid4()),
            "batch_id": str(uuid4()),
            "batch_number": 1,
            "total_batches": 1,
            "products": [],
        }

        await _make_router(publisher)(SupplierEvents.SUPPLIER_PRODUCTS_FETCHED, payload)

        kwargs = publisher.publish_an_event.await_args.kwargs
        assert kwargs["exchange"] is publisher.exchange
        assert kwargs["routing_key"] == SupplierEvents.SUPPLIER_PRODUCTS_FETCHED

    async def test_unroutable_event_type_fails_loudly(self) -> None:
        """An unrouted type must raise so the relay retries instead of dropping."""
        with pytest.raises(ValueError, match="Unsupported supplier outbox event type"):
            await _make_router(_make_publisher())("cj.order.teleported", {})


class TestRoutingKeys:
    """The bindings consumers declare must match the keys we publish under."""

    @pytest.mark.parametrize("event_type", list(OUTBOX_EVENTS))
    def test_cj_events_match_the_consumer_bindings(self, event_type) -> None:
        # order_service binds "cj.order.*"; notification_service binds "cj.order.#".
        assert str(event_type).startswith("cj.order.")
        assert len(str(event_type).split(".")) == 3

    def test_cj_events_do_not_collide_with_the_order_binding(self) -> None:
        # notification_service's order queue binds "order.#". If a CJ event ever
        # matched it, both handlers would claim the same event id and one would
        # silently drop it.
        for event_type in OUTBOX_EVENTS:
            assert not str(event_type).startswith("order.")

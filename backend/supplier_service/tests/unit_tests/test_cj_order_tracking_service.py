"""Unit tests for CJOrderTrackingService."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from enums.cj_order_enums import CJOrderAttemptStatus, CJRemoteOrderStatus
from service_layer.cj_api_client import CJDropshippingAPIError
from service_layer.cj_order_tracking_service import (
    CJOrderSnapshot,
    CJOrderTrackingService,
    CJRemoteOrderStatusMapper,
    TrackedOrder,
)
from shared.enums.event_enums import OrderEvents
from shared.settings import get_settings


TEST_ORDER_ID = uuid4()
TEST_USER_ID = uuid4()
TEST_CJ_ORDER_NUMBER = "CJORDER789"
TEST_TRACKING_NUMBER = "CJP123456789CN"


def _make_attempt(**overrides):
    fields = {
        "order_id": TEST_ORDER_ID,
        "user_id": TEST_USER_ID,
        "user_email": "buyer@example.com",
        "status": CJOrderAttemptStatus.CREATED,
        "cj_order_number": TEST_CJ_ORDER_NUMBER,
        "cj_order_status": None,
        "tracking_number": None,
        "logistic_name": None,
        "shipped_at": None,
        "delivered_at": None,
        "last_polled_at": None,
        "last_error": None,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _tracked_order() -> TrackedOrder:
    return TrackedOrder(
        order_id=TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        user_email="buyer@example.com",
        cj_order_number=TEST_CJ_ORDER_NUMBER,
        status=CJOrderAttemptStatus.CREATED,
    )


def _snapshot(**overrides) -> CJOrderSnapshot:
    fields = {
        "lifecycle": CJRemoteOrderStatus.SHIPPED,
        "raw_status": "SHIPPED",
        "tracking_number": TEST_TRACKING_NUMBER,
        "logistic_name": "CJPacket Ordinary",
    }
    fields.update(overrides)
    return CJOrderSnapshot(**fields)


@pytest.fixture
def tracking(monkeypatch):
    """A service whose database layer is replaced by in-memory doubles.

    Returns the service alongside the attempt row and the list of outbox events
    the service queued, so tests can assert on both state and emissions.
    """
    attempt = _make_attempt()
    outbox_events: list[tuple[str, object]] = []

    repository = MagicMock()
    repository.get_for_update = AsyncMock(return_value=attempt)
    repository.update = AsyncMock()
    repository.claim_due_for_tracking = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "service_layer.cj_order_tracking_service.CJOrderAttemptRepository",
        lambda session: repository,
    )

    outbox_service = MagicMock()

    async def _add(event_type, payload):
        outbox_events.append((event_type, payload))

    outbox_service.add_outbox_event = AsyncMock(side_effect=_add)
    monkeypatch.setattr(
        "service_layer.cj_order_tracking_service.OutboxEventService",
        lambda repository: outbox_service,
    )

    database = MagicMock()

    @asynccontextmanager
    async def transaction():
        session = MagicMock()
        session.flush = AsyncMock()
        yield session

    database.transaction = transaction

    api_client = MagicMock()
    api_client.get_order_detail = AsyncMock(
        return_value={
            "result": True,
            "code": 200,
            "data": {
                "orderStatus": "SHIPPED",
                "trackNumber": TEST_TRACKING_NUMBER,
                "logisticName": "CJPacket Ordinary",
            },
        }
    )

    service = CJOrderTrackingService(
        settings=get_settings(),
        database=database,
        api_client=api_client,
        logger=MagicMock(),
    )
    return SimpleNamespace(
        service=service,
        attempt=attempt,
        events=outbox_events,
        repository=repository,
    )


class TestStatusMapper:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("SHIPPED", CJRemoteOrderStatus.SHIPPED),
            ("In Transit", CJRemoteOrderStatus.SHIPPED),
            ("DELIVERED", CJRemoteOrderStatus.DELIVERED),
            ("Completed", CJRemoteOrderStatus.DELIVERED),
            ("CANCELLED", CJRemoteOrderStatus.CANCELLED),
            ("canceled", CJRemoteOrderStatus.CANCELLED),
            ("UNSHIPPED", CJRemoteOrderStatus.PENDING),
            ("CREATED", CJRemoteOrderStatus.PENDING),
            ("something-new", CJRemoteOrderStatus.UNKNOWN),
            (None, CJRemoteOrderStatus.UNKNOWN),
        ],
    )
    def test_maps_cj_vocabulary(self, raw, expected) -> None:
        assert CJRemoteOrderStatusMapper().map(raw) == expected


class TestParseSnapshot:
    def test_reads_status_and_tracking(self, tracking) -> None:
        snapshot = tracking.service.parse_snapshot(
            {
                "data": {
                    "orderStatus": "SHIPPED",
                    "trackNumber": TEST_TRACKING_NUMBER,
                    "logisticName": "CJPacket Ordinary",
                }
            }
        )

        assert snapshot.lifecycle == CJRemoteOrderStatus.SHIPPED
        assert snapshot.tracking_number == TEST_TRACKING_NUMBER
        assert snapshot.logistic_name == "CJPacket Ordinary"

    def test_accepts_a_single_element_list_payload(self, tracking) -> None:
        snapshot = tracking.service.parse_snapshot(
            {"data": [{"orderStatus": "DELIVERED"}]}
        )

        assert snapshot.lifecycle == CJRemoteOrderStatus.DELIVERED

    def test_missing_data_is_unknown_not_an_error(self, tracking) -> None:
        snapshot = tracking.service.parse_snapshot({"result": False, "data": None})

        assert snapshot.lifecycle == CJRemoteOrderStatus.UNKNOWN
        assert snapshot.tracking_number is None


class TestApplySnapshot:
    async def test_shipped_records_tracking_and_emits_event(self, tracking) -> None:
        outcome = await tracking.service.apply_snapshot(_tracked_order(), _snapshot())

        assert outcome == CJOrderAttemptStatus.SHIPPED
        assert tracking.attempt.status == CJOrderAttemptStatus.SHIPPED
        assert tracking.attempt.tracking_number == TEST_TRACKING_NUMBER
        assert tracking.attempt.shipped_at is not None

        event_type, payload = tracking.events[0]
        assert event_type == OrderEvents.CJ_ORDER_SHIPPED
        assert payload.event_type == OrderEvents.CJ_ORDER_SHIPPED
        assert payload.order_id == TEST_ORDER_ID
        assert payload.user_email == "buyer@example.com"
        assert payload.tracking_number == TEST_TRACKING_NUMBER
        assert payload.cj_order_number == TEST_CJ_ORDER_NUMBER
        assert TEST_TRACKING_NUMBER in payload.tracking_url
        assert payload.service == "supplier-service"

    async def test_shipped_without_tracking_number_waits(self, tracking) -> None:
        outcome = await tracking.service.apply_snapshot(
            _tracked_order(), _snapshot(tracking_number=None)
        )

        assert outcome is None
        assert tracking.attempt.status == CJOrderAttemptStatus.CREATED
        assert tracking.events == []

    async def test_shipped_twice_emits_once(self, tracking) -> None:
        await tracking.service.apply_snapshot(_tracked_order(), _snapshot())
        outcome = await tracking.service.apply_snapshot(_tracked_order(), _snapshot())

        assert outcome is None
        assert len(tracking.events) == 1

    async def test_delivered_from_created_emits_shipped_then_delivered(self, tracking) -> None:
        outcome = await tracking.service.apply_snapshot(
            _tracked_order(),
            _snapshot(lifecycle=CJRemoteOrderStatus.DELIVERED, raw_status="DELIVERED"),
        )

        assert outcome == CJOrderAttemptStatus.DELIVERED
        assert [event_type for event_type, _ in tracking.events] == [
            OrderEvents.CJ_ORDER_SHIPPED,
            OrderEvents.CJ_ORDER_DELIVERED,
        ]
        assert tracking.attempt.delivered_at is not None

    async def test_delivered_after_shipped_emits_only_delivered(self, tracking) -> None:
        tracking.attempt.status = CJOrderAttemptStatus.SHIPPED
        tracking.attempt.tracking_number = TEST_TRACKING_NUMBER

        await tracking.service.apply_snapshot(
            _tracked_order(),
            _snapshot(lifecycle=CJRemoteOrderStatus.DELIVERED, raw_status="DELIVERED"),
        )

        assert [event_type for event_type, _ in tracking.events] == [
            OrderEvents.CJ_ORDER_DELIVERED
        ]

    async def test_cj_cancellation_triggers_saga_compensation(self, tracking) -> None:
        outcome = await tracking.service.apply_snapshot(
            _tracked_order(),
            _snapshot(lifecycle=CJRemoteOrderStatus.CANCELLED, raw_status="CANCELLED"),
        )

        assert outcome == CJOrderAttemptStatus.REJECTED
        assert tracking.attempt.status == CJOrderAttemptStatus.REJECTED
        assert "CANCELLED" in tracking.attempt.last_error

        event_type, payload = tracking.events[0]
        assert event_type == OrderEvents.CJ_ORDER_FAILED
        assert payload.order_id == TEST_ORDER_ID
        assert TEST_CJ_ORDER_NUMBER in payload.reason

    async def test_pending_status_only_records_raw_status(self, tracking) -> None:
        outcome = await tracking.service.apply_snapshot(
            _tracked_order(),
            _snapshot(
                lifecycle=CJRemoteOrderStatus.PENDING,
                raw_status="UNSHIPPED",
                tracking_number=None,
            ),
        )

        assert outcome is None
        assert tracking.attempt.cj_order_status == "UNSHIPPED"
        assert tracking.events == []

    async def test_terminal_attempt_is_never_reopened(self, tracking) -> None:
        tracking.attempt.status = CJOrderAttemptStatus.DELIVERED

        outcome = await tracking.service.apply_snapshot(
            _tracked_order(),
            _snapshot(lifecycle=CJRemoteOrderStatus.CANCELLED, raw_status="CANCELLED"),
        )

        assert outcome is None
        assert tracking.attempt.status == CJOrderAttemptStatus.DELIVERED
        assert tracking.events == []

    async def test_missing_attempt_row_is_a_no_op(self, tracking) -> None:
        tracking.repository.get_for_update = AsyncMock(return_value=None)

        assert await tracking.service.apply_snapshot(_tracked_order(), _snapshot()) is None

    async def test_row_without_email_advances_but_sends_nothing(self, tracking) -> None:
        tracking.attempt.user_email = None

        outcome = await tracking.service.apply_snapshot(_tracked_order(), _snapshot())

        assert outcome == CJOrderAttemptStatus.SHIPPED
        assert tracking.events == []


class TestPollOpenOrders:
    async def test_reports_each_transition(self, tracking, monkeypatch) -> None:
        monkeypatch.setattr(
            tracking.service, "lease_due_orders", AsyncMock(return_value=[_tracked_order()])
        )

        report = await tracking.service.poll_open_orders()

        assert report.polled == 1
        assert report.shipped == 1
        assert report.errors == 0

    async def test_cj_outage_is_counted_not_raised(self, tracking, monkeypatch) -> None:
        monkeypatch.setattr(
            tracking.service, "lease_due_orders", AsyncMock(return_value=[_tracked_order()])
        )
        tracking.service.api_client.get_order_detail = AsyncMock(
            side_effect=CJDropshippingAPIError("CJ is down")
        )

        report = await tracking.service.poll_open_orders()

        assert report.errors == 1
        assert report.shipped == 0
        assert tracking.events == []

    async def test_one_bad_order_does_not_stop_the_batch(self, tracking, monkeypatch) -> None:
        other = TrackedOrder(
            order_id=uuid4(),
            user_id=TEST_USER_ID,
            user_email="buyer@example.com",
            cj_order_number="CJORDER-OTHER",
            status=CJOrderAttemptStatus.CREATED,
        )
        monkeypatch.setattr(
            tracking.service,
            "lease_due_orders",
            AsyncMock(return_value=[other, _tracked_order()]),
        )
        tracking.service.api_client.get_order_detail = AsyncMock(
            side_effect=[
                CJDropshippingAPIError("CJ is down"),
                {"data": {"orderStatus": "SHIPPED", "trackNumber": TEST_TRACKING_NUMBER}},
            ]
        )

        report = await tracking.service.poll_open_orders()

        assert report.polled == 2
        assert report.errors == 1
        assert report.shipped == 1

    async def test_nothing_due_makes_no_cj_calls(self, tracking) -> None:
        report = await tracking.service.poll_open_orders()

        assert report.polled == 0
        tracking.service.api_client.get_order_detail.assert_not_awaited()

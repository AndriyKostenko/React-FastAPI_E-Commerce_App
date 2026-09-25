"""Unit tests for confirming and paying CJ orders from the CJ balance."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import service_layer.cj_order_payment_service as payment_module
from enums.cj_order_enums import CJOrderAttemptStatus
from service_layer.cj_api_client import CJDropshippingAPIError
from service_layer.cj_order_payment_service import CJOrderPaymentService, CJPaymentPending
from shared.contracts.events import OrderConfirmedEvent
from shared.enums.event_enums import OrderEvents


CJ_ORDER = "CJ-2607"
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _settings(**overrides):
    values = {
        "CJ_USD_TO_CAD_RATE": Decimal("1.40"),
        "CJ_PRICE_MARKUP_MULTIPLIER": Decimal("2.00"),
        "CJ_ORDER_COST_TOLERANCE": Decimal("0.15"),
        "CJ_PAYMENT_RETRY_INTERVAL_MINUTES": 10,
        "CJ_PAYMENT_MAX_WAIT_HOURS": 24,
        "CJ_PAYMENT_BATCH_SIZE": 50,
        "CJ_PAYMENT_LEASE_MINUTES": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _Store:
    """In-memory stand-in for the cj_order_attempts table and the outbox."""

    def __init__(self) -> None:
        self.attempts: dict = {}
        self.outbox: list[tuple[str, object]] = []

    def repository(self, _session):
        store = self

        class _Repo:
            async def get_by_field(self, _field, value):
                return store.attempts.get(value)

            async def get_for_update(self, order_id):
                return store.attempts.get(order_id)

            async def update(self, attempt):
                attempt.date_updated = NOW

            async def get_due_for_payment(self, *, updated_before, limit):
                return [
                    attempt
                    for attempt in store.attempts.values()
                    if attempt.status in CJOrderAttemptStatus.awaiting_payment()
                    and attempt.date_updated <= updated_before
                ][:limit]

        return _Repo()

    def outbox_service(self, _repository):
        store = self

        class _Outbox:
            async def add_outbox_event(self, event_type, payload):
                store.outbox.append((event_type, payload))

        return _Outbox()


@pytest.fixture
def store(monkeypatch) -> _Store:
    store = _Store()
    monkeypatch.setattr(payment_module, "CJOrderAttemptRepository", store.repository)
    monkeypatch.setattr(payment_module, "OutboxEventService", store.outbox_service)
    monkeypatch.setattr(payment_module, "OutboxRepository", lambda **_kwargs: None)
    return store


def _attempt(store: _Store, status=CJOrderAttemptStatus.CREATED, **overrides):
    order_id = uuid4()
    attempt = SimpleNamespace(
        order_id=order_id,
        user_id=uuid4(),
        user_email="buyer@example.com",
        status=status,
        cj_order_number=CJ_ORDER,
        expected_max_amount_usd=Decimal("30.00"),
        cj_order_amount_usd=None,
        paid_at=None,
        payment_attempts=0,
        payment_leased_until=None,
        last_error=None,
        date_created=NOW,
        date_updated=NOW,
    )
    for key, value in overrides.items():
        setattr(attempt, key, value)
    store.attempts[order_id] = attempt
    return attempt


def _detail(status: str, amount: str | None = "20.00") -> dict:
    return {"code": 200, "result": True, "data": {"orderStatus": status, "orderAmount": amount}}


def _service(api_client, **settings_overrides) -> CJOrderPaymentService:
    database = MagicMock()

    @asynccontextmanager
    async def transaction():
        yield MagicMock()

    database.transaction = transaction
    return CJOrderPaymentService(
        settings=_settings(**settings_overrides),
        database=database,
        api_client=api_client,
        logger=MagicMock(),
    )


def _api(*details: dict, balance: str = "100.00") -> MagicMock:
    api = MagicMock()
    api.get_order_detail = AsyncMock(side_effect=list(details))
    api.confirm_order = AsyncMock(return_value={"code": 200, "result": True})
    api.get_balance = AsyncMock(return_value={"code": 200, "result": True, "data": {"amount": balance}})
    api.pay_balance = AsyncMock(return_value={"code": 200, "result": True})
    return api


class TestAdvance:
    async def test_created_order_is_confirmed_then_paid(self, store):
        attempt = _attempt(store)
        api = _api(_detail("CREATED"), _detail("UNPAID"))

        status = await _service(api).advance(attempt.order_id)

        assert status == CJOrderAttemptStatus.PAID
        api.confirm_order.assert_awaited_once_with(CJ_ORDER)
        api.pay_balance.assert_awaited_once_with(CJ_ORDER)
        assert attempt.cj_order_amount_usd == Decimal("20.00")
        assert attempt.paid_at is not None
        [(event_type, payload)] = store.outbox
        assert event_type == OrderEvents.CJ_ORDER_PAID
        assert payload.cj_order_number == CJ_ORDER
        assert payload.amount_usd == Decimal("20.00")

    async def test_order_cj_already_holds_paid_is_recorded_without_paying_again(self, store):
        attempt = _attempt(store, status=CJOrderAttemptStatus.CONFIRMED)
        api = _api(_detail("UNSHIPPED"))

        status = await _service(api).advance(attempt.order_id)

        assert status == CJOrderAttemptStatus.PAID
        api.pay_balance.assert_not_awaited()
        assert [event for event, _ in store.outbox] == [OrderEvents.CJ_ORDER_PAID]

    async def test_low_balance_waits_for_funds_without_paying(self, store):
        attempt = _attempt(store, status=CJOrderAttemptStatus.CONFIRMED)
        api = _api(_detail("UNPAID"), balance="5.00")

        status = await _service(api).advance(attempt.order_id)

        assert status == CJOrderAttemptStatus.AWAITING_FUNDS
        assert "cannot cover" in attempt.last_error
        api.pay_balance.assert_not_awaited()
        assert store.outbox == []

    async def test_bill_above_expected_maximum_is_held_for_review(self, store):
        attempt = _attempt(store, status=CJOrderAttemptStatus.CONFIRMED)
        api = _api(_detail("UNPAID", amount="45.00"))

        status = await _service(api).advance(attempt.order_id)

        assert status == CJOrderAttemptStatus.RECONCILIATION_REQUIRED
        api.get_balance.assert_not_awaited()
        api.pay_balance.assert_not_awaited()

    async def test_payment_error_after_cj_took_the_money_counts_as_paid(self, store):
        attempt = _attempt(store, status=CJOrderAttemptStatus.CONFIRMED)
        api = _api(_detail("UNPAID"), _detail("PENDING"))
        api.pay_balance = AsyncMock(side_effect=CJDropshippingAPIError("timeout"))

        status = await _service(api).advance(attempt.order_id)

        assert status == CJOrderAttemptStatus.PAID

    async def test_payment_error_with_order_still_unpaid_is_retried_later(self, store):
        attempt = _attempt(store, status=CJOrderAttemptStatus.CONFIRMED)
        api = _api(_detail("UNPAID"), _detail("UNPAID"))
        api.pay_balance = AsyncMock(side_effect=CJDropshippingAPIError("gateway error"))

        with pytest.raises(CJPaymentPending):
            await _service(api).advance(attempt.order_id)
        assert attempt.status == CJOrderAttemptStatus.CONFIRMED
        assert store.outbox == []

    async def test_order_cj_cancelled_fails_and_compensates(self, store):
        attempt = _attempt(store)
        api = _api(_detail("CANCELLED"))

        status = await _service(api).advance(attempt.order_id)

        assert status == CJOrderAttemptStatus.FAILED
        assert [event for event, _ in store.outbox] == [OrderEvents.CJ_ORDER_FAILED]

    async def test_paid_order_is_left_alone(self, store):
        attempt = _attempt(store, status=CJOrderAttemptStatus.PAID)
        api = _api()

        status = await _service(api).advance(attempt.order_id)

        assert status == CJOrderAttemptStatus.PAID
        api.get_order_detail.assert_not_awaited()


class TestPaymentLease:
    """
    The order.confirmed consumer and the payment cron both call advance(); the
    lease keeps them from both walking an order to pay_balance at once.
    """

    async def test_a_held_lease_stops_a_second_runner_before_it_touches_cj(self, store) -> None:
        held_until = datetime.now(timezone.utc) + timedelta(minutes=5)
        attempt = _attempt(store, payment_leased_until=held_until)
        api = _api(_detail("CREATED"), _detail("UNPAID"), _detail("UNPAID"))

        with pytest.raises(CJPaymentPending, match="already in progress"):
            await _service(api).advance(attempt.order_id)

        api.get_order_detail.assert_not_awaited()
        api.pay_balance.assert_not_awaited()
        assert attempt.payment_leased_until == held_until  # someone else's lease is left alone

    async def test_the_lease_is_released_after_a_payment(self, store) -> None:
        attempt = _attempt(store)
        api = _api(_detail("CREATED"), _detail("UNPAID"), _detail("UNPAID"))

        await _service(api).advance(attempt.order_id)

        assert attempt.payment_leased_until is None
        assert attempt.payment_attempts == 1

    async def test_the_lease_is_released_when_the_walk_fails(self, store) -> None:
        attempt = _attempt(store)
        api = _api(_detail("CREATED"))
        api.confirm_order = AsyncMock(side_effect=CJDropshippingAPIError("CJ down"))
        api.get_order_detail = AsyncMock(side_effect=[_detail("CREATED"), _detail("CREATED")])

        with pytest.raises(CJPaymentPending):
            await _service(api).advance(attempt.order_id)

        assert attempt.payment_leased_until is None  # the next run is not locked out

    async def test_an_expired_lease_from_a_crashed_runner_is_taken_over(self, store) -> None:
        attempt = _attempt(store, payment_leased_until=datetime.now(timezone.utc) - timedelta(seconds=1))
        api = _api(_detail("CREATED"), _detail("UNPAID"), _detail("UNPAID"))

        await _service(api).advance(attempt.order_id)

        api.pay_balance.assert_awaited_once()


class TestAdvanceDue:
    async def test_order_unpaid_past_the_maximum_wait_is_failed(self, store):
        old = NOW - timedelta(hours=25)
        stale = _attempt(store, status=CJOrderAttemptStatus.AWAITING_FUNDS, date_created=old, date_updated=old,
                         last_error="CJ balance 5 USD cannot cover 20 USD")
        api = _api()

        report = await _service(api).advance_due(now=NOW)

        assert report.failed == 1
        assert stale.status == CJOrderAttemptStatus.FAILED
        [(event_type, payload)] = store.outbox
        assert event_type == OrderEvents.CJ_ORDER_FAILED
        assert "cannot cover" in payload.reason

    async def test_recently_touched_orders_are_not_retried_yet(self, store):
        _attempt(store, status=CJOrderAttemptStatus.CONFIRMED, date_updated=NOW - timedelta(minutes=2))
        api = _api()

        report = await _service(api).advance_due(now=NOW)

        assert report.as_dict()["paid"] == 0
        api.get_order_detail.assert_not_awaited()

    async def test_due_order_is_paid(self, store):
        due = NOW - timedelta(minutes=30)
        _attempt(store, status=CJOrderAttemptStatus.CONFIRMED, date_created=due, date_updated=due)
        api = _api(_detail("UNPAID"))

        report = await _service(api).advance_due(now=NOW)

        assert report.paid == 1


class TestExpectedMaximum:
    def test_bounds_product_cost_from_shelf_price_plus_freight(self):
        event = OrderConfirmedEvent(
            order_id=uuid4(),
            user_id=uuid4(),
            user_email="buyer@example.com",
            items=[
                {"product_id": str(uuid4()), "quantity": 2, "price": 28.99, "fulfillment_type": "cj"}
            ],
            shipping_cost_usd=Decimal("5.00"),
        )

        ceiling = CJOrderPaymentService.expected_max_amount_usd(event, _settings())

        # 57.98 CAD / 1.40 / 2.00 = 20.707 USD goods + 5.00 freight, x 1.15
        assert ceiling == Decimal("29.56")

    def test_legacy_order_without_quoted_freight_has_no_ceiling(self):
        event = OrderConfirmedEvent(order_id=uuid4(), user_id=uuid4(), user_email="buyer@example.com")

        assert CJOrderPaymentService.expected_max_amount_usd(event, _settings()) is None

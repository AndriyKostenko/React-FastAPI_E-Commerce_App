from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

from shared.enums.status_enums import OrderStatus
from tests.constants import (
    TEST_AMOUNT,
    TEST_ORDER_ID,
    TEST_PAYMENT_INTENT_ID,
    TEST_PRODUCT_ID,
    TEST_USER_ID,
    TEST_CURRENCY,
)
from schemas.order_schemas import OrderItemBase


def _detailed_order(order):
    fulfillment = SimpleNamespace(
        fulfillment_type="catalog",
        product_name="Widget",
        customization=None,
        variant_snapshot=None,
    )
    order.items = [
        SimpleNamespace(
            id=TEST_PRODUCT_ID,
            product_id=TEST_PRODUCT_ID,
            variant_id=None,
            quantity=2,
            price=49.99,
            fulfillment=fulfillment,
        )
    ]
    order.address = SimpleNamespace(
        street="123 Test St",
        city="Calgary",
        province="AB",
        postal_code="T1T 1T1",
        country="Canada",
        country_code="CA",
        name="Test User",
        phone="+14035550123",
    )
    return order


async def test_payment_alone_does_not_confirm(order_service_unit, mock_order_orm):
    service = order_service_unit
    service.outbox_event_service.add_outbox_event = AsyncMock()
    service.repository.get_by_id = AsyncMock(return_value=mock_order_orm)

    result = await service.record_payment_authorized(
        TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        amount_cents=round(TEST_AMOUNT * 100),
        currency=TEST_CURRENCY,
        payment_intent_id=TEST_PAYMENT_INTENT_ID,
    )

    assert result.status == OrderStatus.PENDING
    assert not any(
        call.kwargs.get("event_type") == "order.confirmed"
        for call in service.outbox_event_service.add_outbox_event.call_args_list
    )


async def test_confirmation_requires_both_gates_in_any_order(
    order_service_unit, mock_order_orm
):
    service = order_service_unit
    service.outbox_event_service.add_outbox_event = AsyncMock()
    detailed = _detailed_order(mock_order_orm)
    service.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
    service.repository.get_with_fulfillment = AsyncMock(return_value=detailed)

    await service.record_inventory_succeeded(TEST_ORDER_ID)
    assert mock_order_orm.status == OrderStatus.PENDING

    await service.record_payment_authorized(
        TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        amount_cents=round(TEST_AMOUNT * 100),
        currency=TEST_CURRENCY,
        payment_intent_id=TEST_PAYMENT_INTENT_ID,
    )

    assert mock_order_orm.status == OrderStatus.CONFIRMED
    event_types = [
        call.kwargs.get("event_type")
        for call in service.outbox_event_service.add_outbox_event.call_args_list
    ]
    assert event_types.count("order.confirmed") == 1
    # No CJ line: nothing external can still fail, so the card is charged now.
    assert event_types.count("payment.capture.requested") == 1


async def test_payment_mismatch_compensates_reserved_inventory(
    order_service_unit, mock_order_orm
):
    service = order_service_unit
    service.outbox_event_service.add_outbox_event = AsyncMock()
    saga = await service.saga_repository.get_for_update(TEST_ORDER_ID)
    saga.inventory_status = "reserved"
    service.saga_repository.get_for_update.reset_mock()
    service.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
    service.order_item_service.get_items_by_order_id = AsyncMock(
        return_value=[
            OrderItemBase(
                order_id=TEST_ORDER_ID,
                product_id=TEST_PRODUCT_ID,
                variant_id=None,
                quantity=2,
                price=49.99,
                fulfillment_type="catalog",
            )
        ]
    )

    await service.record_payment_authorized(
        TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        amount_cents=1,
        currency=TEST_CURRENCY,
        payment_intent_id=TEST_PAYMENT_INTENT_ID,
    )

    assert mock_order_orm.status == OrderStatus.CANCELLED
    event_types = [
        call.kwargs["event_type"]
        for call in service.outbox_event_service.add_outbox_event.call_args_list
    ]
    assert "order.cancelled" in event_types
    assert "inventory.release.requested" in event_types


async def test_late_authorization_releases_hold_without_repeating_compensation(
    order_service_unit, mock_order_orm
):
    service = order_service_unit
    mock_order_orm.status = OrderStatus.CANCELLED
    service.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
    service.outbox_event_service.add_outbox_event = AsyncMock()

    result = await service.record_payment_authorized(
        TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        amount_cents=1,
        currency="wrong",
        payment_intent_id="pi_late",
    )

    assert result.status == OrderStatus.CANCELLED
    service.repository.update.assert_not_awaited()
    calls = service.outbox_event_service.add_outbox_event.call_args_list
    assert [call.kwargs["event_type"] for call in calls] == ["payment.release.requested"]
    assert calls[0].kwargs["payload"].payment_intent_id == "pi_late"


def _cj_detailed_order(order):
    detailed = _detailed_order(order)
    detailed.items[0].fulfillment.fulfillment_type = "cj"
    return detailed


async def test_cj_order_is_confirmed_but_not_charged_until_cj_is_paid(
    order_service_unit, mock_order_orm
):
    service = order_service_unit
    service.outbox_event_service.add_outbox_event = AsyncMock()
    detailed = _cj_detailed_order(mock_order_orm)
    service.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
    service.repository.get_with_fulfillment = AsyncMock(return_value=detailed)
    saga = await service.saga_repository.get_for_update(TEST_ORDER_ID)
    saga.inventory_status = "reserved"

    await service.record_payment_authorized(
        TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        amount_cents=round(TEST_AMOUNT * 100),
        currency=TEST_CURRENCY,
        payment_intent_id=TEST_PAYMENT_INTENT_ID,
    )

    assert mock_order_orm.status == OrderStatus.CONFIRMED
    event_types = [
        call.kwargs["event_type"]
        for call in service.outbox_event_service.add_outbox_event.call_args_list
    ]
    assert "order.confirmed" in event_types
    assert "payment.capture.requested" not in event_types

    service.outbox_event_service.add_outbox_event.reset_mock()
    cj_line = SimpleNamespace(order_item_id=TEST_PRODUCT_ID, fulfillment_type="cj", status="pending")
    service.fulfillment_status_service.get_lines = AsyncMock(return_value=[cj_line])

    await service.record_cj_order_paid(TEST_ORDER_ID)

    service.fulfillment_status_service.mark_lines.assert_awaited_once()
    assert service.fulfillment_status_service.mark_lines.await_args.args[1] == "submitted"
    assert [
        call.kwargs["event_type"]
        for call in service.outbox_event_service.add_outbox_event.call_args_list
    ] == ["payment.capture.requested"]
    assert saga.payment_status == "capture_requested"

    # A redelivered cj.order.paid must not request a second capture.
    service.outbox_event_service.add_outbox_event.reset_mock()
    await service.record_cj_order_paid(TEST_ORDER_ID)
    service.outbox_event_service.add_outbox_event.assert_not_awaited()


async def test_lapsed_payment_after_supplier_was_paid_keeps_the_order(
    order_service_unit, mock_order_orm
):
    service = order_service_unit
    mock_order_orm.status = OrderStatus.CONFIRMED
    service.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
    service.outbox_event_service.add_outbox_event = AsyncMock()
    service.fulfillment_status_service.get_lines = AsyncMock(
        return_value=[SimpleNamespace(status="submitted", blocks_cancellation=True)]
    )

    await service.record_payment_cancelled(TEST_ORDER_ID, "authorization expired")

    assert mock_order_orm.status == OrderStatus.CONFIRMED
    service.outbox_event_service.add_outbox_event.assert_not_awaited()


async def test_cancelled_payment_before_fulfillment_cancels_the_order(
    order_service_unit, mock_order_orm
):
    service = order_service_unit
    service.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
    service.outbox_event_service.add_outbox_event = AsyncMock()

    await service.record_payment_cancelled(TEST_ORDER_ID, "Payment cancelled: abandoned")

    assert mock_order_orm.status == OrderStatus.CANCELLED
    assert "order.cancelled" in [
        call.kwargs["event_type"]
        for call in service.outbox_event_service.add_outbox_event.call_args_list
    ]

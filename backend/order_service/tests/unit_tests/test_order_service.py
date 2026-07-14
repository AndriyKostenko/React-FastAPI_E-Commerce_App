"""Unit tests for OrderService business logic (all DB/IO replaced with mocks)."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from service_layer.order_service import OrderService
from shared.schemas.order_schemas import (
    CreateOrder, UpdateOrder, OrderItemBase, OrderAddressBase, OrderSchema
)
from shared.schemas.event_schemas import OrderCreatedEvent
from shared.enums.status_enums import OrderStatus, OrderDeliveryStatus
from exceptions.order_exceptions import (
    OrderNotFoundError, OrdersNotFoundError, DuplicatePaymentIntentError, OrderNotCancellableError
)
from tests.constants import (
    TEST_ORDER_ID, TEST_USER_ID, TEST_EMAIL, TEST_AMOUNT, TEST_CURRENCY,
    TEST_PAYMENT_INTENT_ID, TEST_ORDER_ADDRESS_ID, TEST_PRODUCT_ID, TEST_DATETIME,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_create_order(**overrides) -> CreateOrder:
    defaults = dict(
        user_id=TEST_USER_ID,
        user_email=TEST_EMAIL,
        amount=TEST_AMOUNT,
        currency=TEST_CURRENCY,
        payment_intent_id=TEST_PAYMENT_INTENT_ID,
        products=[
            MagicMock(id=TEST_PRODUCT_ID, name="Widget", price=49.99, quantity=2)
        ],
        address=MagicMock(
            street="123 Test St",
            city="Testville",
            province="TS",
            postal_code="T1T 1T1",
        ),
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


def _make_order_schema(**overrides) -> OrderSchema:
    data = dict(
        id=TEST_ORDER_ID,
        user_id=TEST_USER_ID,
        user_email=TEST_EMAIL,
        amount=TEST_AMOUNT,
        currency=TEST_CURRENCY,
        status=OrderStatus.PENDING,
        delivery_status=OrderDeliveryStatus.PENDING,
        payment_intent_id=TEST_PAYMENT_INTENT_ID,
        address_id=TEST_ORDER_ADDRESS_ID,
        date_created=TEST_DATETIME,
        date_updated=None,
    )
    data.update(overrides)
    return OrderSchema(**data)


def _make_address_base() -> OrderAddressBase:
    return OrderAddressBase(
        id=TEST_ORDER_ADDRESS_ID,
        user_id=TEST_USER_ID,
        street="123 Test St",
        city="Testville",
        province="TS",
        postal_code="T1T 1T1",
    )


def _make_item_base() -> OrderItemBase:
    return OrderItemBase(
        order_id=TEST_ORDER_ID,
        product_id=TEST_PRODUCT_ID,
        quantity=2,
        price=49.99,
    )


# ---------------------------------------------------------------------------
# create_order
# ---------------------------------------------------------------------------

class TestCreateOrder:
    async def test_create_order_success(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        """create_order returns an OrderSchema when all sub-services succeed."""
        svc = order_service_unit
        address_base = _make_address_base()
        item_base = _make_item_base()

        svc.order_address_service.create_order_address = AsyncMock(return_value=address_base)
        svc.repository.create = AsyncMock(return_value=mock_order_orm)
        svc.order_item_service.create_order_items = AsyncMock(return_value=[item_base])
        svc.outbox_event_service.add_outbox_event = AsyncMock(return_value=None)

        order_data = _make_create_order()
        result = await svc.create_order(order_data)

        assert isinstance(result, OrderSchema)
        assert result.id == mock_order_orm.id
        assert result.status == OrderStatus.PENDING
        assert svc.outbox_event_service.add_outbox_event.call_count == 2

    async def test_create_order_raises_duplicate_payment_intent(
        self, order_service_unit: OrderService
    ):
        """create_order re-raises IntegrityError as DuplicatePaymentIntentError."""
        svc = order_service_unit
        address_base = _make_address_base()

        svc.order_address_service.create_order_address = AsyncMock(return_value=address_base)
        svc.repository.create = AsyncMock(side_effect=IntegrityError("dup", {}, None))
        svc.order_item_service.create_order_items = AsyncMock()
        svc.outbox_event_service.add_outbox_event = AsyncMock()

        order_data = _make_create_order()
        with pytest.raises(DuplicatePaymentIntentError):
            await svc.create_order(order_data)

    async def test_create_order_emits_two_outbox_events(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        """create_order emits ORDER_CREATED and INVENTORY_RESERVE_REQUESTED events."""
        svc = order_service_unit
        address_base = _make_address_base()
        item_base = _make_item_base()

        svc.order_address_service.create_order_address = AsyncMock(return_value=address_base)
        svc.repository.create = AsyncMock(return_value=mock_order_orm)
        svc.order_item_service.create_order_items = AsyncMock(return_value=[item_base])
        svc.outbox_event_service.add_outbox_event = AsyncMock(return_value=None)

        await svc.create_order(_make_create_order())

        event_types = [
            call.kwargs["event_type"]
            for call in svc.outbox_event_service.add_outbox_event.call_args_list
        ]
        assert "order.created" in event_types
        assert "inventory.reserve.requested" in event_types


# ---------------------------------------------------------------------------
# cancel_order
# ---------------------------------------------------------------------------

class TestCancelOrder:
    async def test_cancel_pending_order_success(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        """cancel_order PENDING → CANCELLED and emits ORDER_CANCELLED event."""
        svc = order_service_unit
        mock_order_orm.status = OrderStatus.PENDING
        cancelled_orm = MagicMock(**vars(mock_order_orm))
        cancelled_orm.status = OrderStatus.CANCELLED

        svc.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
        svc.repository.update_by_id = AsyncMock(return_value=cancelled_orm)
        svc.outbox_event_service.add_outbox_event = AsyncMock(return_value=None)

        result = await svc.cancel_order(TEST_ORDER_ID, reason="Changed mind")

        svc.repository.update_by_id.assert_awaited_once_with(
            TEST_ORDER_ID, data={"status": OrderStatus.CANCELLED}
        )
        assert svc.outbox_event_service.add_outbox_event.call_count == 1

    async def test_cancel_confirmed_order_also_releases_inventory(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        """cancel_order CONFIRMED order emits both ORDER_CANCELLED and INVENTORY_RELEASE_REQUESTED."""
        svc = order_service_unit
        mock_order_orm.status = OrderStatus.CONFIRMED
        cancelled_orm = MagicMock()
        cancelled_orm.id = TEST_ORDER_ID
        cancelled_orm.user_id = TEST_USER_ID
        cancelled_orm.user_email = TEST_EMAIL
        cancelled_orm.amount = TEST_AMOUNT
        cancelled_orm.currency = TEST_CURRENCY
        cancelled_orm.status = OrderStatus.CANCELLED
        cancelled_orm.delivery_status = OrderDeliveryStatus.PENDING
        cancelled_orm.payment_intent_id = TEST_PAYMENT_INTENT_ID
        cancelled_orm.address_id = TEST_ORDER_ADDRESS_ID
        cancelled_orm.cj_order_number = None
        cancelled_orm.date_created = TEST_DATETIME
        cancelled_orm.date_updated = None

        item_base = _make_item_base()
        svc.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
        svc.repository.update_by_id = AsyncMock(return_value=cancelled_orm)
        svc.order_item_service.get_items_by_order_id = AsyncMock(return_value=[item_base])
        svc.outbox_event_service.add_outbox_event = AsyncMock(return_value=None)

        await svc.cancel_order(TEST_ORDER_ID, reason="Fraud")

        event_types = [
            call.kwargs["event_type"]
            for call in svc.outbox_event_service.add_outbox_event.call_args_list
        ]
        assert "order.cancelled" in event_types
        assert "inventory.release.requested" in event_types
        assert svc.outbox_event_service.add_outbox_event.call_count == 2

    async def test_cancel_already_cancelled_raises(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        """cancel_order raises OrderNotCancellableError if already CANCELLED."""
        svc = order_service_unit
        mock_order_orm.status = OrderStatus.CANCELLED
        svc.repository.get_by_id = AsyncMock(return_value=mock_order_orm)

        with pytest.raises(OrderNotCancellableError):
            await svc.cancel_order(TEST_ORDER_ID, reason="test")

    async def test_cancel_order_not_found_raises(self, order_service_unit: OrderService):
        """cancel_order raises OrderNotFoundError when order does not exist."""
        svc = order_service_unit
        svc.repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(OrderNotFoundError):
            await svc.cancel_order(TEST_ORDER_ID, reason="test")


# ---------------------------------------------------------------------------
# get_order_by_id
# ---------------------------------------------------------------------------

class TestGetOrderById:
    async def test_get_order_by_id_success(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        svc = order_service_unit
        svc.repository.get_by_id = AsyncMock(return_value=mock_order_orm)

        result = await svc.get_order_by_id(TEST_ORDER_ID)

        assert isinstance(result, OrderSchema)
        assert result.id == TEST_ORDER_ID

    async def test_get_order_by_id_not_found_raises(self, order_service_unit: OrderService):
        svc = order_service_unit
        svc.repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(OrderNotFoundError):
            await svc.get_order_by_id(TEST_ORDER_ID)


# ---------------------------------------------------------------------------
# get_orders
# ---------------------------------------------------------------------------

class TestGetOrders:
    async def test_get_orders_returns_list(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        svc = order_service_unit
        svc.repository.get_all = AsyncMock(return_value=[mock_order_orm])

        result = await svc.get_orders()

        assert len(result) == 1
        assert isinstance(result[0], OrderSchema)

    async def test_get_orders_empty_raises(self, order_service_unit: OrderService):
        svc = order_service_unit
        svc.repository.get_all = AsyncMock(return_value=None)

        with pytest.raises(OrdersNotFoundError):
            await svc.get_orders()


# ---------------------------------------------------------------------------
# get_orders_by_user_id
# ---------------------------------------------------------------------------

class TestGetOrdersByUserId:
    async def test_get_orders_by_user_id_success(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        svc = order_service_unit
        svc.repository.get_many_by_field = AsyncMock(return_value=[mock_order_orm])

        result = await svc.get_orders_by_user_id(TEST_USER_ID)

        assert len(result) == 1
        assert result[0].user_id == TEST_USER_ID

    async def test_get_orders_by_user_id_not_found_raises(
        self, order_service_unit: OrderService
    ):
        svc = order_service_unit
        svc.repository.get_many_by_field = AsyncMock(return_value=None)

        with pytest.raises(OrdersNotFoundError):
            await svc.get_orders_by_user_id(TEST_USER_ID)


# ---------------------------------------------------------------------------
# update_order
# ---------------------------------------------------------------------------

class TestUpdateOrder:
    async def test_update_order_without_confirmed_transition(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        """update_order without status→CONFIRMED does NOT emit outbox event."""
        svc = order_service_unit
        mock_order_orm.status = OrderStatus.PENDING
        updated_orm = MagicMock()
        updated_orm.id = TEST_ORDER_ID
        updated_orm.user_id = TEST_USER_ID
        updated_orm.user_email = TEST_EMAIL
        updated_orm.amount = TEST_AMOUNT
        updated_orm.currency = TEST_CURRENCY
        updated_orm.status = OrderStatus.PENDING
        updated_orm.delivery_status = OrderDeliveryStatus.DELIVERED
        updated_orm.payment_intent_id = TEST_PAYMENT_INTENT_ID
        updated_orm.address_id = TEST_ORDER_ADDRESS_ID
        updated_orm.cj_order_number = None
        updated_orm.date_created = TEST_DATETIME
        updated_orm.date_updated = None

        svc.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
        svc.repository.update_by_id = AsyncMock(return_value=updated_orm)
        svc.outbox_event_service.add_outbox_event = AsyncMock(return_value=None)

        order_data = UpdateOrder(delivery_status=OrderDeliveryStatus.DELIVERED, amount=TEST_AMOUNT)
        result = await svc.update_order(TEST_ORDER_ID, order_data)

        assert isinstance(result, OrderSchema)
        svc.outbox_event_service.add_outbox_event.assert_not_awaited()

    async def test_update_order_with_confirmed_transition_emits_event(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        """update_order status→CONFIRMED emits ORDER_CONFIRMED outbox event."""
        svc = order_service_unit
        mock_order_orm.status = OrderStatus.PENDING
        confirmed_orm = MagicMock()
        confirmed_orm.id = TEST_ORDER_ID
        confirmed_orm.user_id = TEST_USER_ID
        confirmed_orm.user_email = TEST_EMAIL
        confirmed_orm.amount = TEST_AMOUNT
        confirmed_orm.currency = TEST_CURRENCY
        confirmed_orm.status = OrderStatus.CONFIRMED
        confirmed_orm.delivery_status = OrderDeliveryStatus.PENDING
        confirmed_orm.payment_intent_id = TEST_PAYMENT_INTENT_ID
        confirmed_orm.address_id = TEST_ORDER_ADDRESS_ID
        confirmed_orm.cj_order_number = None
        confirmed_orm.date_created = TEST_DATETIME
        confirmed_orm.date_updated = None
        confirmed_orm.items = [
            MagicMock(product_id=TEST_PRODUCT_ID, variant_id=None, quantity=2, price=49.99)
        ]
        confirmed_orm.address = MagicMock()
        confirmed_orm.address.street = "123 Test St"
        confirmed_orm.address.city = "Testville"
        confirmed_orm.address.province = "TS"
        confirmed_orm.address.postal_code = "T1T 1T1"
        confirmed_orm.address.country = "Canada"
        confirmed_orm.address.country_code = "CA"
        confirmed_orm.address.name = "Test User"
        confirmed_orm.address.phone = "+1234567890"

        svc.repository.get_by_id = AsyncMock(side_effect=[mock_order_orm, confirmed_orm])
        svc.repository.update_by_id = AsyncMock(return_value=confirmed_orm)
        svc.outbox_event_service.add_outbox_event = AsyncMock(return_value=None)

        order_data = UpdateOrder(status=OrderStatus.CONFIRMED, amount=TEST_AMOUNT)
        await svc.update_order(TEST_ORDER_ID, order_data)

        svc.outbox_event_service.add_outbox_event.assert_awaited_once()
        call_kwargs = svc.outbox_event_service.add_outbox_event.call_args.kwargs
        assert call_kwargs["event_type"] == "order.confirmed"

    async def test_update_order_already_confirmed_does_not_re_emit(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        """update_order CONFIRMED→CONFIRMED does NOT emit a second event."""
        svc = order_service_unit
        mock_order_orm.status = OrderStatus.CONFIRMED
        confirmed_orm = MagicMock()
        confirmed_orm.id = TEST_ORDER_ID
        confirmed_orm.user_id = TEST_USER_ID
        confirmed_orm.user_email = TEST_EMAIL
        confirmed_orm.amount = TEST_AMOUNT
        confirmed_orm.currency = TEST_CURRENCY
        confirmed_orm.status = OrderStatus.CONFIRMED
        confirmed_orm.delivery_status = OrderDeliveryStatus.PENDING
        confirmed_orm.payment_intent_id = TEST_PAYMENT_INTENT_ID
        confirmed_orm.address_id = TEST_ORDER_ADDRESS_ID
        confirmed_orm.cj_order_number = None
        confirmed_orm.date_created = TEST_DATETIME
        confirmed_orm.date_updated = None

        svc.repository.get_by_id = AsyncMock(return_value=mock_order_orm)
        svc.repository.update_by_id = AsyncMock(return_value=confirmed_orm)
        svc.outbox_event_service.add_outbox_event = AsyncMock(return_value=None)

        order_data = UpdateOrder(status=OrderStatus.CONFIRMED, amount=TEST_AMOUNT)
        await svc.update_order(TEST_ORDER_ID, order_data)

        svc.outbox_event_service.add_outbox_event.assert_not_awaited()

    async def test_update_order_not_found_raises(self, order_service_unit: OrderService):
        svc = order_service_unit
        svc.repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(OrderNotFoundError):
            await svc.update_order(TEST_ORDER_ID, UpdateOrder(amount=TEST_AMOUNT))


# ---------------------------------------------------------------------------
# update_order_status
# ---------------------------------------------------------------------------

class TestUpdateOrderStatus:
    async def test_update_order_status_success(
        self, order_service_unit: OrderService, mock_order_orm: MagicMock
    ):
        svc = order_service_unit
        mock_order_orm.status = OrderStatus.CONFIRMED
        svc.repository.update_by_id = AsyncMock(return_value=mock_order_orm)

        result = await svc.update_order_status(TEST_ORDER_ID, OrderStatus.CONFIRMED)

        assert isinstance(result, OrderSchema)
        svc.repository.update_by_id.assert_awaited_once_with(
            TEST_ORDER_ID, data={"status": OrderStatus.CONFIRMED}
        )


# ---------------------------------------------------------------------------
# delete_order_by_id
# ---------------------------------------------------------------------------

class TestDeleteOrder:
    async def test_delete_order_success(self, order_service_unit: OrderService):
        svc = order_service_unit
        svc.repository.delete_by_id = AsyncMock(return_value=True)

        await svc.delete_order_by_id(TEST_ORDER_ID)

        svc.repository.delete_by_id.assert_awaited_once_with(TEST_ORDER_ID)

    async def test_delete_order_not_found_raises(self, order_service_unit: OrderService):
        svc = order_service_unit
        svc.repository.delete_by_id = AsyncMock(return_value=None)

        with pytest.raises(OrderNotFoundError):
            await svc.delete_order_by_id(TEST_ORDER_ID)

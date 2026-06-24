from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from shared.enums.event_enums import OrderEvents
from events_consumer.cart_event_consumer import CartEventConsumer


@pytest.fixture
def consumer() -> CartEventConsumer:
    return CartEventConsumer(logger=MagicMock())


@pytest.fixture
def order_created_message() -> dict:
    order_id = str(uuid4())
    return {
        "event_id": str(uuid4()),
        "event_type": OrderEvents.ORDER_CREATED,
        "timestamp": "2024-01-01T12:00:00+00:00",
        "service": "order-service",
        "order_id": order_id,
        "user_id": str(uuid4()),
        "user_email": "test@example.com",
        "items": [
            {
                "order_id": order_id,
                "product_id": str(uuid4()),
                "quantity": 2,
                "price": 9.99,
            },
        ],
        "total_amount": 19.98,
    }


@pytest.fixture
def mock_cart_service() -> MagicMock:
    service = MagicMock()
    service.clear_cart = AsyncMock()
    return service


@pytest.fixture
def mock_idempotency_service() -> MagicMock:
    svc = MagicMock()
    svc.try_claim_event = AsyncMock(return_value=True)
    svc.mark_event_as_processed = AsyncMock()
    svc.release_claim = AsyncMock()
    return svc


async def test_handle_order_created_clears_cart(
    consumer: CartEventConsumer,
    order_created_message: dict,
    mock_cart_service: MagicMock,
    mock_idempotency_service: MagicMock,
) -> None:
    consumer.idempotency_service = mock_idempotency_service

    with patch.object(
        consumer, "_get_cart_service", return_value=_async_generator(mock_cart_service)
    ):
        await consumer.handle_order_created(order_created_message)

    mock_cart_service.clear_cart.assert_awaited_once_with(
        user_id=UUID(order_created_message["user_id"])
    )
    mock_idempotency_service.try_claim_event.assert_awaited_once()
    mock_idempotency_service.mark_event_as_processed.assert_awaited_once()


async def test_handle_order_created_skips_duplicate(
    consumer: CartEventConsumer,
    order_created_message: dict,
    mock_cart_service: MagicMock,
    mock_idempotency_service: MagicMock,
) -> None:
    mock_idempotency_service.try_claim_event = AsyncMock(return_value=False)
    consumer.idempotency_service = mock_idempotency_service

    with patch.object(
        consumer, "_get_cart_service", return_value=_async_generator(mock_cart_service)
    ):
        await consumer.handle_order_created(order_created_message)

    mock_cart_service.clear_cart.assert_not_awaited()
    mock_idempotency_service.mark_event_as_processed.assert_not_awaited()


async def test_handle_order_created_releases_claim_on_error(
    consumer: CartEventConsumer,
    order_created_message: dict,
    mock_cart_service: MagicMock,
    mock_idempotency_service: MagicMock,
) -> None:
    mock_cart_service.clear_cart = AsyncMock(side_effect=RuntimeError("DB error"))
    consumer.idempotency_service = mock_idempotency_service

    with patch.object(
        consumer, "_get_cart_service", return_value=_async_generator(mock_cart_service)
    ):
        with pytest.raises(RuntimeError):
            await consumer.handle_order_created(order_created_message)

    mock_idempotency_service.release_claim.assert_awaited_once()


async def test_handle_order_event_routes_to_created_handler(
    consumer: CartEventConsumer,
    order_created_message: dict,
    mock_cart_service: MagicMock,
    mock_idempotency_service: MagicMock,
) -> None:
    consumer.idempotency_service = mock_idempotency_service

    with patch.object(consumer, "handle_order_created") as mock_handle:
        with patch.object(
            consumer, "_get_cart_service", return_value=_async_generator(mock_cart_service)
        ):
            await consumer.handle_order_event(order_created_message)

    mock_handle.assert_awaited_once_with(order_created_message)


def _async_generator(value):
    async def _gen():
        yield value

    return _gen()

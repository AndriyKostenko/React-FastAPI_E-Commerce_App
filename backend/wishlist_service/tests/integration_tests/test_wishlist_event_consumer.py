from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from shared.enums.event_enums import UserEvents
from events_consumer.wishlist_event_consumer import WishlistEventConsumer


@pytest.fixture
def consumer() -> WishlistEventConsumer:
    return WishlistEventConsumer(logger=MagicMock())


@pytest.fixture
def user_deleted_message() -> dict:
    return {
        "event_id": str(uuid4()),
        "event_type": UserEvents.USER_DELETED,
        "timestamp": "2024-01-01T12:00:00+00:00",
        "service": "user-service",
        "user_id": str(uuid4()),
        "user_email": "test@example.com",
    }


@pytest.fixture
def mock_wishlist_service() -> MagicMock:
    service = MagicMock()
    service.delete_wishlist_by_user_id = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_idempotency_service() -> MagicMock:
    svc = MagicMock()
    svc.try_claim_event = AsyncMock(return_value=True)
    svc.mark_event_as_processed = AsyncMock()
    svc.release_claim = AsyncMock()
    return svc


async def test_handle_user_deleted_deletes_wishlist(
    consumer: WishlistEventConsumer,
    user_deleted_message: dict,
    mock_wishlist_service: MagicMock,
    mock_idempotency_service: MagicMock,
) -> None:
    consumer.idempotency_service = mock_idempotency_service

    with patch.object(
        consumer, "_get_wishlist_service", return_value=_async_generator(mock_wishlist_service)
    ):
        await consumer.handle_user_deleted(user_deleted_message)

    mock_wishlist_service.delete_wishlist_by_user_id.assert_awaited_once_with(
        user_id=UUID(user_deleted_message["user_id"])
    )
    mock_idempotency_service.try_claim_event.assert_awaited_once()
    mock_idempotency_service.mark_event_as_processed.assert_awaited_once()


async def test_handle_user_deleted_skips_duplicate(
    consumer: WishlistEventConsumer,
    user_deleted_message: dict,
    mock_wishlist_service: MagicMock,
    mock_idempotency_service: MagicMock,
) -> None:
    mock_idempotency_service.try_claim_event = AsyncMock(return_value=False)
    consumer.idempotency_service = mock_idempotency_service

    with patch.object(
        consumer, "_get_wishlist_service", return_value=_async_generator(mock_wishlist_service)
    ):
        await consumer.handle_user_deleted(user_deleted_message)

    mock_wishlist_service.delete_wishlist_by_user_id.assert_not_awaited()
    mock_idempotency_service.mark_event_as_processed.assert_not_awaited()


async def test_handle_user_deleted_releases_claim_on_error(
    consumer: WishlistEventConsumer,
    user_deleted_message: dict,
    mock_wishlist_service: MagicMock,
    mock_idempotency_service: MagicMock,
) -> None:
    mock_wishlist_service.delete_wishlist_by_user_id = AsyncMock(side_effect=RuntimeError("DB error"))
    consumer.idempotency_service = mock_idempotency_service

    with patch.object(
        consumer, "_get_wishlist_service", return_value=_async_generator(mock_wishlist_service)
    ):
        with pytest.raises(RuntimeError):
            await consumer.handle_user_deleted(user_deleted_message)

    mock_idempotency_service.release_claim.assert_awaited_once()


async def test_handle_user_event_routes_to_deleted_handler(
    consumer: WishlistEventConsumer,
    user_deleted_message: dict,
    mock_wishlist_service: MagicMock,
    mock_idempotency_service: MagicMock,
) -> None:
    consumer.idempotency_service = mock_idempotency_service

    with patch.object(consumer, "handle_user_deleted") as mock_handle:
        with patch.object(
            consumer, "_get_wishlist_service", return_value=_async_generator(mock_wishlist_service)
        ):
            await consumer.handle_user_event(user_deleted_message)

    mock_handle.assert_awaited_once_with(user_deleted_message)


def _async_generator(value):
    async def _gen():
        yield value

    return _gen()

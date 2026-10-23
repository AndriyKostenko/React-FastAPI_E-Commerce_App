"""
A deleted account's cart, through the real cart consumer: the test database
and Redis (the event's idempotency claim) are real, and the message is the
user.deleted event user-service publishes.
"""

from collections.abc import AsyncGenerator
from decimal import Decimal
from logging import getLogger
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from contracts.events import UserDeletedEvent
from database_layer.cart_repository import CartRepository
from events_consumer.cart_event_consumer import CartEventConsumer
from infrastructure.idempotency.idempotency_service import IdempotencyEventService
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.cart_models import Cart, CartItem
from service_config import settings

# The Redis connection is bound to the session loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def consumer(
    integration_client: AsyncClient,  # creates the schema and truncates afterwards
    test_database_session_manager: TestDatabaseSessionManager,
) -> AsyncGenerator[CartEventConsumer, None]:
    # A prefix of its own, so claims from other runs never collide.
    idempotency = IdempotencyEventService(
        service_prefix=f"cart-test-{uuid4().hex[:8]}", logger=getLogger("test"), redis_url=settings.CART_SERVICE_REDIS_URL
    )
    await idempotency.connect()
    try:
        yield CartEventConsumer(logger=getLogger("test"), database=test_database_session_manager, idempotency=idempotency)
    finally:
        await idempotency.close()


async def _cart_with_lines(db: TestDatabaseSessionManager, user_id: UUID, lines: int = 2) -> None:
    async with db.transaction() as session:
        cart = Cart(user_id=user_id)
        session.add(cart)
        await session.flush()
        for _ in range(lines):
            await CartRepository(session).add_item_to_cart(cart.id, uuid4(), 1, Decimal("10.00"))


async def _counts(db: TestDatabaseSessionManager, user_id: UUID) -> tuple[int, int]:
    async with db.transaction() as session:
        carts = await session.scalar(select(func.count()).select_from(Cart).where(Cart.user_id == user_id))
        lines = await session.scalar(
            select(func.count()).select_from(CartItem).join(Cart).where(Cart.user_id == user_id)
        )
    return carts, lines


def _user_deleted(user_id: UUID) -> dict:
    return UserDeletedEvent(user_email="gone@example.com", user_id=user_id).model_dump(mode="json")


async def test_the_deleted_accounts_cart_goes_with_its_lines_and_others_stay(
    consumer: CartEventConsumer, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    gone, staying = uuid4(), uuid4()
    await _cart_with_lines(test_database_session_manager, gone)
    await _cart_with_lines(test_database_session_manager, staying)

    await consumer.handle_user_event(_user_deleted(gone))

    assert await _counts(test_database_session_manager, gone) == (0, 0)
    assert await _counts(test_database_session_manager, staying) == (1, 2)


async def test_a_redelivered_event_changes_nothing(
    consumer: CartEventConsumer, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    user_id = uuid4()
    await _cart_with_lines(test_database_session_manager, user_id)
    message = _user_deleted(user_id)

    await consumer.handle_user_event(message)
    # A cart made again after deletion is not touched by a stale redelivery.
    await _cart_with_lines(test_database_session_manager, user_id, lines=1)
    await consumer.handle_user_event(message)

    assert await _counts(test_database_session_manager, user_id) == (1, 1)


async def test_an_account_without_a_cart_is_fine(consumer: CartEventConsumer) -> None:
    await consumer.handle_user_event(_user_deleted(uuid4()))

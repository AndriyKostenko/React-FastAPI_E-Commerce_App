"""
Concurrent add-to-cart against the real test database. Only Postgres can show
a lost update, so nothing here is mocked: two transactions really overlap.
"""

import asyncio
from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from database_layer.cart_repository import CartRepository
from models.cart_models import Cart, CartItem
from shared.managers.test_database_session_manager import TestDatabaseSessionManager


async def test_concurrent_adds_of_the_same_product_are_not_lost(
    integration_client: AsyncClient,  # creates the schema and truncates afterwards
    test_database_session_manager: TestDatabaseSessionManager,
) -> None:
    product_id = uuid4()
    async with test_database_session_manager.transaction() as session:
        cart = Cart(user_id=uuid4())
        session.add(cart)
        await session.flush()
        cart_id = cart.id
        await CartRepository(session).add_item_to_cart(cart_id, product_id, 1, Decimal("10.00"))

    async def add_one() -> None:
        async with test_database_session_manager.transaction() as session:
            await CartRepository(session).add_item_to_cart(cart_id, product_id, 1, Decimal("10.00"))
            # Keep the transaction open so the two adds genuinely overlap.
            await asyncio.sleep(0.2)

    await asyncio.gather(add_one(), add_one())

    async with test_database_session_manager.transaction() as session:
        item = await session.get(CartItem, (await _item_id(session, cart_id)))
    # 1 + 1 + 1. Without the row lock both adds read 1 and wrote 2.
    assert item is not None and item.quantity == 3


async def _item_id(session, cart_id):
    return (await session.execute(select(CartItem.id).where(CartItem.cart_id == cart_id))).scalar_one()

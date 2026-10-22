from uuid import UUID
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.cart_models import Cart, CartItem
from infrastructure.database_layer.database_layer import BaseRepository


class CartRepository(BaseRepository[Cart]):
    """
    Repository for cart-specific database operations.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, Cart)

    async def get_cart_by_user_id(self, user_id: UUID) -> Cart | None:
        """Get cart by user ID with items loaded."""
        return await self.get_by_field("user_id", user_id)

    async def lock_cart(self, cart_id: UUID) -> None:
        """Serialise changes to one cart until the transaction ends."""
        await self.session.execute(select(Cart.id).where(Cart.id == cart_id).with_for_update())

    async def find_item(self, cart_id: UUID, product_id: UUID) -> CartItem | None:
        result = await self.session.execute(
            select(CartItem).where(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
        )
        return result.scalar_one_or_none()

    async def count_items(self, cart_id: UUID) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(CartItem).where(CartItem.cart_id == cart_id)
        ) or 0

    async def add_item_to_cart(self, cart_id: UUID, product_id: UUID, quantity: int, price_snapshot: Decimal) -> CartItem:
        # Locked for the read-modify-write below: two concurrent adds of the same
        # product both read the old quantity and one increment was lost.
        result = await self.session.execute(
            select(CartItem)
            .where(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
            .with_for_update()
        )
        item = result.scalar_one_or_none()

        if item:
            item.quantity += quantity
        else:
            item = CartItem(
                cart_id=cart_id, 
                product_id=product_id, 
                quantity=quantity, 
                price_snapshot=price_snapshot
            )
            self.session.add(item)
            
        await self.session.flush()
        return item

    async def update_item_quantity(self, cart_id: UUID, item_id: UUID, quantity: int) -> CartItem | None:
        result = await self.session.execute(
            select(CartItem).where(CartItem.cart_id == cart_id, CartItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item:
            item.quantity = quantity
            await self.session.flush()
        return item

    async def remove_item(self, cart_id: UUID, item_id: UUID) -> bool:
        result = await self.session.execute(
            select(CartItem).where(CartItem.cart_id == cart_id, CartItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item:
            await self.session.delete(item)
            await self.session.flush()
            return True
        return False

    async def clear_cart(self, cart_id: UUID) -> None:
        result = await self.session.execute(
            select(CartItem).where(CartItem.cart_id == cart_id)
        )
        items = result.scalars().all()
        for item in items:
            await self.session.delete(item)
        await self.session.flush()

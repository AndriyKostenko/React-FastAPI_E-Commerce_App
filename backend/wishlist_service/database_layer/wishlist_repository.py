from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.wishlist_models import Wishlist, WishlistItem
from infrastructure.database_layer.database_layer import BaseRepository


class WishlistRepository(BaseRepository[Wishlist]):
    """
    Repository for wishlist-specific database operations.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, Wishlist)

    async def get_wishlist_by_user_id(self, user_id: UUID) -> Wishlist | None:
        """Get wishlist by user ID with items loaded."""
        return await self.get_by_field("user_id", user_id)

    async def lock_wishlist(self, wishlist_id: UUID) -> None:
        """Serialise changes to one wishlist until the transaction ends."""
        await self.session.execute(select(Wishlist.id).where(Wishlist.id == wishlist_id).with_for_update())

    async def holds(self, wishlist_id: UUID, product_id: UUID) -> bool:
        return await self.session.scalar(
            select(WishlistItem.id).where(WishlistItem.wishlist_id == wishlist_id, WishlistItem.product_id == product_id)
        ) is not None

    async def count_items(self, wishlist_id: UUID) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(WishlistItem).where(WishlistItem.wishlist_id == wishlist_id)
        ) or 0

    async def add_item(self, wishlist_id: UUID, product_id: UUID) -> WishlistItem:
        """Add a product to a wishlist. Raises on duplicate."""
        result = await self.session.execute(
            select(WishlistItem).where(
                WishlistItem.wishlist_id == wishlist_id,
                WishlistItem.product_id == product_id
            )
        )
        existing_item = result.scalar_one_or_none()
        if existing_item is not None:
            return existing_item

        item = WishlistItem(wishlist_id=wishlist_id, product_id=product_id)
        self.session.add(item)
        await self.session.flush()
        return item

    async def remove_item(self, wishlist_id: UUID, item_id: UUID) -> bool:
        """Remove an item from a wishlist by item ID."""
        result = await self.session.execute(
            select(WishlistItem).where(
                WishlistItem.wishlist_id == wishlist_id,
                WishlistItem.id == item_id
            )
        )
        item = result.scalar_one_or_none()
        if item:
            await self.session.delete(item)
            await self.session.flush()
            return True
        return False

    async def delete_wishlist_by_user_id(self, user_id: UUID) -> bool:
        """Delete the wishlist (and cascading items) for a user."""
        result = await self.session.execute(
            select(Wishlist).where(Wishlist.user_id == user_id)
        )
        wishlist = result.scalar_one_or_none()
        if wishlist:
            await self.session.delete(wishlist)
            await self.session.flush()
            return True
        return False

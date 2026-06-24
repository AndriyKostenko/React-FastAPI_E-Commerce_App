from uuid import UUID

from aiohttp import ClientSession

from database_layer.wishlist_repository import WishlistRepository
from models.wishlist_models import Wishlist
from shared.schemas.wishlist_schemas import WishlistSchema, AddWishlistItem
from shared.shared_instances import settings, logger
from exceptions.wishlist_exceptions import (
    WishlistNotFoundError,
    WishlistItemNotFoundError,
    ProductNotFoundError,
)


class WishlistService:
    def __init__(self, repository: WishlistRepository):
        self.repository = repository

    async def _get_or_create_wishlist_model(self, user_id: UUID) -> Wishlist:
        """Fetch the user's wishlist or create a new one if it doesn't exist."""
        wishlist = await self.repository.get_wishlist_by_user_id(user_id)
        if wishlist is not None:
            return wishlist

        new_wishlist = Wishlist(user_id=user_id)
        await self.repository.create(new_wishlist)

        wishlist = await self.repository.get_wishlist_by_user_id(user_id)
        if wishlist is None:
            raise WishlistNotFoundError(user_id)
        return wishlist

    async def _validate_product_exists(self, http_session: ClientSession, product_id: UUID) -> None:
        """Validate that a product exists by calling the product service."""
        url = f"{settings.PRODUCT_SERVICE_URL}{settings.PRODUCT_SERVICE_URL_API_VERSION}/products/{product_id}"
        try:
            async with http_session.get(url) as response:
                if response.status == 404:
                    raise ProductNotFoundError(product_id)
                if response.status >= 500:
                    logger.error(f"Product service returned {response.status} for product {product_id}")
                    raise ProductNotFoundError(product_id)
        except ProductNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to validate product {product_id}: {e}")
            raise ProductNotFoundError(product_id)

    async def get_or_create_wishlist(self, user_id: UUID) -> WishlistSchema:
        wishlist = await self._get_or_create_wishlist_model(user_id)
        return WishlistSchema.model_validate(wishlist)

    async def add_item_to_wishlist(
        self,
        user_id: UUID,
        item_data: AddWishlistItem,
        http_session: ClientSession | None = None,
    ) -> WishlistSchema:
        wishlist = await self._get_or_create_wishlist_model(user_id)

        if http_session is not None:
            await self._validate_product_exists(http_session, item_data.product_id)

        await self.repository.add_item(
            wishlist_id=wishlist.id,
            product_id=item_data.product_id,
        )
        await self.repository.session.refresh(wishlist)
        return WishlistSchema.model_validate(wishlist)

    async def remove_item_from_wishlist(self, user_id: UUID, item_id: UUID) -> WishlistSchema:
        wishlist = await self.repository.get_wishlist_by_user_id(user_id)
        if wishlist is None:
            raise WishlistNotFoundError(user_id)

        success = await self.repository.remove_item(
            wishlist_id=wishlist.id,
            item_id=item_id,
        )
        if not success:
            raise WishlistItemNotFoundError(item_id)

        await self.repository.session.refresh(wishlist)
        return WishlistSchema.model_validate(wishlist)

    async def delete_wishlist_by_user_id(self, user_id: UUID) -> bool:
        """Delete the wishlist for a user. Used by the event consumer."""
        return await self.repository.delete_wishlist_by_user_id(user_id)

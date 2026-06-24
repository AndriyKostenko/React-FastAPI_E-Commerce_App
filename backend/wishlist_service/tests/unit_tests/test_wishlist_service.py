"""Unit tests for WishlistService business logic (all DB/IO replaced with mocks)."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID

import pytest

from service_layer.wishlist_service import WishlistService
from exceptions.wishlist_exceptions import (
    WishlistNotFoundError,
    WishlistItemNotFoundError,
)
from models.wishlist_models import Wishlist, WishlistItem
from shared.schemas.wishlist_schemas import WishlistSchema, AddWishlistItem
from shared.shared_instances import test_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wishlist_item_orm(
    item_id: UUID = test_settings.TEST_WISHLIST_ITEM_ID,
    wishlist_id: UUID = test_settings.TEST_WISHLIST_ID,
    product_id: UUID = test_settings.TEST_PRODUCT_ID,
) -> WishlistItem:
    item = WishlistItem(
        wishlist_id=wishlist_id,
        product_id=product_id,
    )
    item.id = item_id
    item.date_created = test_settings.TEST_DATETIME
    item.date_updated = test_settings.TEST_DATETIME
    return item


def _make_wishlist_orm(
    wishlist_id: UUID = test_settings.TEST_WISHLIST_ID,
    user_id: UUID = test_settings.TEST_USER_ID,
    items: list[WishlistItem] | None = None,
) -> Wishlist:
    wishlist = Wishlist(user_id=user_id)
    wishlist.id = wishlist_id
    wishlist.date_created = test_settings.TEST_DATETIME
    wishlist.date_updated = test_settings.TEST_DATETIME
    wishlist.items = items if items is not None else []
    return wishlist


def _make_add_item_data(product_id: UUID = test_settings.TEST_PRODUCT_ID) -> AddWishlistItem:
    return AddWishlistItem(product_id=product_id)


# ---------------------------------------------------------------------------
# _get_or_create_wishlist_model / get_or_create_wishlist
# ---------------------------------------------------------------------------

class TestGetOrCreateWishlist:
    async def test_get_or_create_wishlist_returns_existing_wishlist(
        self, wishlist_service_unit: WishlistService, mock_wishlist_orm: Wishlist
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.get_wishlist_by_user_id = AsyncMock(return_value=mock_wishlist_orm)

        result = await svc.get_or_create_wishlist(test_settings.TEST_USER_ID)

        assert isinstance(result, WishlistSchema)
        assert result.id == test_settings.TEST_WISHLIST_ID
        assert result.user_id == test_settings.TEST_USER_ID
        assert len(result.items) == 1
        svc.repository.get_wishlist_by_user_id.assert_awaited_once_with(test_settings.TEST_USER_ID)
        svc.repository.create.assert_not_awaited()

    async def test_get_or_create_wishlist_creates_new_wishlist_when_missing(
        self, wishlist_service_unit: WishlistService, empty_wishlist_orm: Wishlist
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.get_wishlist_by_user_id = AsyncMock(side_effect=[None, empty_wishlist_orm])
        svc.repository.create = AsyncMock(return_value=empty_wishlist_orm)

        result = await svc.get_or_create_wishlist(test_settings.TEST_USER_ID)

        assert isinstance(result, WishlistSchema)
        assert result.id == test_settings.TEST_WISHLIST_ID
        assert result.user_id == test_settings.TEST_USER_ID
        svc.repository.create.assert_awaited_once()

    async def test_get_or_create_wishlist_raises_when_create_fails_to_persist(
        self, wishlist_service_unit: WishlistService
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.get_wishlist_by_user_id = AsyncMock(return_value=None)
        svc.repository.create = AsyncMock(return_value=None)

        with pytest.raises(WishlistNotFoundError):
            await svc.get_or_create_wishlist(test_settings.TEST_USER_ID)


# ---------------------------------------------------------------------------
# add_item_to_wishlist
# ---------------------------------------------------------------------------

class TestAddItemToWishlist:
    async def test_add_item_to_wishlist_new_item(
        self, wishlist_service_unit: WishlistService, mock_wishlist_orm: Wishlist
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.get_wishlist_by_user_id = AsyncMock(return_value=mock_wishlist_orm)
        svc.repository.add_item = AsyncMock(return_value=mock_wishlist_orm.items[0])

        item_data = _make_add_item_data()
        result = await svc.add_item_to_wishlist(test_settings.TEST_USER_ID, item_data)

        assert isinstance(result, WishlistSchema)
        svc.repository.add_item.assert_awaited_once_with(
            wishlist_id=test_settings.TEST_WISHLIST_ID,
            product_id=test_settings.TEST_PRODUCT_ID,
        )
        svc.repository.session.refresh.assert_awaited_once_with(mock_wishlist_orm)

    async def test_add_item_to_wishlist_creates_wishlist_when_missing(
        self, wishlist_service_unit: WishlistService, empty_wishlist_orm: Wishlist
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.get_wishlist_by_user_id = AsyncMock(side_effect=[None, empty_wishlist_orm])
        svc.repository.create = AsyncMock(return_value=empty_wishlist_orm)
        svc.repository.add_item = AsyncMock(return_value=_make_wishlist_item_orm())

        item_data = _make_add_item_data()
        result = await svc.add_item_to_wishlist(test_settings.TEST_USER_ID, item_data)

        assert isinstance(result, WishlistSchema)
        svc.repository.create.assert_awaited_once()
        svc.repository.session.refresh.assert_awaited_once_with(empty_wishlist_orm)

    async def test_add_item_to_wishlist_propagates_repository_error(
        self, wishlist_service_unit: WishlistService, mock_wishlist_orm: Wishlist
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.get_wishlist_by_user_id = AsyncMock(return_value=mock_wishlist_orm)
        svc.repository.add_item = AsyncMock(side_effect=RuntimeError("DB error"))

        with pytest.raises(RuntimeError):
            await svc.add_item_to_wishlist(test_settings.TEST_USER_ID, _make_add_item_data())


# ---------------------------------------------------------------------------
# remove_item_from_wishlist
# ---------------------------------------------------------------------------

class TestRemoveItemFromWishlist:
    async def test_remove_item_from_wishlist_success(
        self, wishlist_service_unit: WishlistService, mock_wishlist_orm: Wishlist
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.get_wishlist_by_user_id = AsyncMock(return_value=mock_wishlist_orm)
        svc.repository.remove_item = AsyncMock(return_value=True)

        result = await svc.remove_item_from_wishlist(
            test_settings.TEST_USER_ID, test_settings.TEST_WISHLIST_ITEM_ID
        )

        assert isinstance(result, WishlistSchema)
        svc.repository.remove_item.assert_awaited_once_with(
            wishlist_id=test_settings.TEST_WISHLIST_ID,
            item_id=test_settings.TEST_WISHLIST_ITEM_ID,
        )
        svc.repository.session.refresh.assert_awaited_once_with(mock_wishlist_orm)

    async def test_remove_item_from_wishlist_not_found(
        self, wishlist_service_unit: WishlistService, mock_wishlist_orm: Wishlist
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.get_wishlist_by_user_id = AsyncMock(return_value=mock_wishlist_orm)
        svc.repository.remove_item = AsyncMock(return_value=False)

        with pytest.raises(WishlistItemNotFoundError):
            await svc.remove_item_from_wishlist(
                test_settings.TEST_USER_ID, test_settings.TEST_WISHLIST_ITEM_ID
            )

    async def test_remove_item_from_wishlist_wishlist_not_found(
        self, wishlist_service_unit: WishlistService
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.get_wishlist_by_user_id = AsyncMock(return_value=None)

        with pytest.raises(WishlistNotFoundError):
            await svc.remove_item_from_wishlist(
                test_settings.TEST_USER_ID, test_settings.TEST_WISHLIST_ITEM_ID
            )


# ---------------------------------------------------------------------------
# delete_wishlist_by_user_id
# ---------------------------------------------------------------------------

class TestDeleteWishlistByUserId:
    async def test_delete_wishlist_by_user_id_success(
        self, wishlist_service_unit: WishlistService
    ) -> None:
        svc = wishlist_service_unit
        svc.repository.delete_wishlist_by_user_id = AsyncMock(return_value=True)

        result = await svc.delete_wishlist_by_user_id(test_settings.TEST_USER_ID)

        assert result is True
        svc.repository.delete_wishlist_by_user_id.assert_awaited_once_with(
            test_settings.TEST_USER_ID
        )

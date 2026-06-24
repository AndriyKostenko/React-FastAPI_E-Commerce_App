"""Unit tests for CartService business logic (all DB/IO replaced with mocks)."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from service_layer.cart_services import CartService, CartNotFoundError, CartItemNotFoundError
from models.cart_models import Cart, CartItem
from shared.schemas.cart_schemas import CartSchema, CartSummary, AddCartItem, UpdateCartItem
from tests.constants import (
    TEST_CART_ID,
    TEST_CART_ITEM_ID,
    TEST_USER_ID,
    TEST_PRODUCT_ID,
    TEST_DATETIME,
    TEST_PRICE_SNAPSHOT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cart_item_orm(
    item_id: str = TEST_CART_ITEM_ID,
    cart_id: str = TEST_CART_ID,
    product_id: str = TEST_PRODUCT_ID,
    quantity: int = 2,
    price_snapshot: Decimal = TEST_PRICE_SNAPSHOT,
) -> CartItem:
    item = CartItem(
        cart_id=cart_id,
        product_id=product_id,
        quantity=quantity,
        price_snapshot=price_snapshot,
    )
    item.id = item_id
    item.date_created = TEST_DATETIME
    item.date_updated = None
    return item


def _make_cart_orm(
    cart_id: str = TEST_CART_ID,
    user_id: str = TEST_USER_ID,
    items: list[CartItem] | None = None,
) -> Cart:
    cart = Cart(user_id=user_id)
    cart.id = cart_id
    cart.date_created = TEST_DATETIME
    cart.date_updated = None
    cart.items = items if items is not None else []
    return cart


def _make_add_item_data(
    product_id: str = TEST_PRODUCT_ID,
    quantity: int = 2,
    price_snapshot: Decimal = TEST_PRICE_SNAPSHOT,
) -> AddCartItem:
    return AddCartItem(
        product_id=product_id,
        quantity=quantity,
        price_snapshot=price_snapshot,
    )


def _make_update_item_data(quantity: int = 5) -> UpdateCartItem:
    return UpdateCartItem(quantity=quantity)


# ---------------------------------------------------------------------------
# _get_or_create_cart_model / get_or_create_cart
# ---------------------------------------------------------------------------

class TestGetOrCreateCart:
    async def test_get_or_create_cart_returns_existing_cart(
        self, cart_service_unit: CartService, mock_cart_orm: Cart
    ) -> None:
        """If the user already has a cart, return it as a schema."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=mock_cart_orm)

        result = await svc.get_or_create_cart(TEST_USER_ID)

        assert isinstance(result, CartSchema)
        assert result.id == TEST_CART_ID
        assert result.user_id == TEST_USER_ID
        assert len(result.items) == 1
        svc.repository.get_cart_by_user_id.assert_awaited_once_with(TEST_USER_ID)
        svc.repository.create.assert_not_awaited()

    async def test_get_or_create_cart_creates_new_cart_when_missing(
        self, cart_service_unit: CartService, empty_cart_orm: Cart
    ) -> None:
        """If no cart exists, create one and return it."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(side_effect=[None, empty_cart_orm])
        svc.repository.create = AsyncMock(return_value=empty_cart_orm)

        result = await svc.get_or_create_cart(TEST_USER_ID)

        assert isinstance(result, CartSchema)
        assert result.id == TEST_CART_ID
        assert result.user_id == TEST_USER_ID
        svc.repository.create.assert_awaited_once()

    async def test_get_or_create_cart_raises_when_create_fails_to_persist(
        self, cart_service_unit: CartService
    ) -> None:
        """If creation succeeds but the cart still can't be fetched, raise CartNotFoundError."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=None)
        svc.repository.create = AsyncMock(return_value=None)

        with pytest.raises(CartNotFoundError):
            await svc.get_or_create_cart(TEST_USER_ID)


# ---------------------------------------------------------------------------
# get_cart_summary
# ---------------------------------------------------------------------------

class TestGetCartSummary:
    async def test_get_cart_summary_with_items(
        self, cart_service_unit: CartService, mock_cart_orm: Cart
    ) -> None:
        """Summary correctly totals items and amount."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=mock_cart_orm)

        result = await svc.get_cart_summary(TEST_USER_ID)

        assert isinstance(result, CartSummary)
        assert result.id == TEST_CART_ID
        assert result.user_id == TEST_USER_ID
        assert result.total_items == 2
        assert result.total_amount == Decimal("19.98")
        assert len(result.items) == 1

    async def test_get_cart_summary_empty_cart(
        self, cart_service_unit: CartService, empty_cart_orm: Cart
    ) -> None:
        """Summary for an empty cart has zero totals."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(side_effect=[None, empty_cart_orm])
        svc.repository.create = AsyncMock(return_value=empty_cart_orm)

        result = await svc.get_cart_summary(TEST_USER_ID)

        assert result.total_items == 0
        assert result.total_amount == Decimal("0")
        assert result.items == []


# ---------------------------------------------------------------------------
# add_item_to_cart
# ---------------------------------------------------------------------------

class TestAddItemToCart:
    async def test_add_item_to_cart_new_item(
        self, cart_service_unit: CartService, mock_cart_orm: Cart
    ) -> None:
        """Adding an item to a cart returns the updated cart."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=mock_cart_orm)
        svc.repository.add_item_to_cart = AsyncMock(return_value=mock_cart_orm.items[0])

        item_data = _make_add_item_data()
        result = await svc.add_item_to_cart(TEST_USER_ID, item_data)

        assert isinstance(result, CartSchema)
        svc.repository.add_item_to_cart.assert_awaited_once_with(
            cart_id=TEST_CART_ID,
            product_id=TEST_PRODUCT_ID,
            quantity=2,
            price_snapshot=TEST_PRICE_SNAPSHOT,
        )
        svc.repository.session.refresh.assert_awaited_once_with(mock_cart_orm)

    async def test_add_item_to_cart_creates_cart_when_missing(
        self, cart_service_unit: CartService, empty_cart_orm: Cart
    ) -> None:
        """If no cart exists, one is created before adding the item."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(side_effect=[None, empty_cart_orm])
        svc.repository.create = AsyncMock(return_value=empty_cart_orm)
        svc.repository.add_item_to_cart = AsyncMock(return_value=_make_cart_item_orm())

        item_data = _make_add_item_data()
        result = await svc.add_item_to_cart(TEST_USER_ID, item_data)

        assert isinstance(result, CartSchema)
        svc.repository.create.assert_awaited_once()
        svc.repository.session.refresh.assert_awaited_once_with(empty_cart_orm)

    async def test_add_item_to_cart_propagates_repository_error(
        self, cart_service_unit: CartService, mock_cart_orm: Cart
    ) -> None:
        """If the repository raises an error while adding, it propagates."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=mock_cart_orm)
        svc.repository.add_item_to_cart = AsyncMock(side_effect=RuntimeError("DB error"))

        with pytest.raises(RuntimeError):
            await svc.add_item_to_cart(TEST_USER_ID, _make_add_item_data())


# ---------------------------------------------------------------------------
# update_item_quantity
# ---------------------------------------------------------------------------

class TestUpdateItemQuantity:
    async def test_update_item_quantity_success(
        self, cart_service_unit: CartService, mock_cart_orm: Cart
    ) -> None:
        """Updating an existing item returns the updated cart."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=mock_cart_orm)
        svc.repository.update_item_quantity = AsyncMock(return_value=mock_cart_orm.items[0])

        item_data = _make_update_item_data(quantity=5)
        result = await svc.update_item_quantity(TEST_USER_ID, TEST_CART_ITEM_ID, item_data)

        assert isinstance(result, CartSchema)
        svc.repository.update_item_quantity.assert_awaited_once_with(
            cart_id=TEST_CART_ID,
            item_id=TEST_CART_ITEM_ID,
            quantity=5,
        )
        svc.repository.session.refresh.assert_awaited_once_with(mock_cart_orm)

    async def test_update_item_quantity_cart_not_found(
        self, cart_service_unit: CartService
    ) -> None:
        """If the user's cart doesn't exist, raise CartNotFoundError."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=None)

        with pytest.raises(CartNotFoundError):
            await svc.update_item_quantity(TEST_USER_ID, TEST_CART_ITEM_ID, _make_update_item_data())

    async def test_update_item_quantity_item_not_found(
        self, cart_service_unit: CartService, mock_cart_orm: Cart
    ) -> None:
        """If the item doesn't exist in the cart, raise CartItemNotFoundError."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=mock_cart_orm)
        svc.repository.update_item_quantity = AsyncMock(return_value=None)

        with pytest.raises(CartItemNotFoundError):
            await svc.update_item_quantity(TEST_USER_ID, TEST_CART_ITEM_ID, _make_update_item_data())


# ---------------------------------------------------------------------------
# remove_item_from_cart
# ---------------------------------------------------------------------------

class TestRemoveItemFromCart:
    async def test_remove_item_from_cart_success(
        self, cart_service_unit: CartService, mock_cart_orm: Cart
    ) -> None:
        """Removing an existing item returns the updated cart."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=mock_cart_orm)
        svc.repository.remove_item = AsyncMock(return_value=True)

        result = await svc.remove_item_from_cart(TEST_USER_ID, TEST_CART_ITEM_ID)

        assert isinstance(result, CartSchema)
        svc.repository.remove_item.assert_awaited_once_with(
            cart_id=TEST_CART_ID,
            item_id=TEST_CART_ITEM_ID,
        )
        svc.repository.session.refresh.assert_awaited_once_with(mock_cart_orm)

    async def test_remove_item_from_cart_not_found(
        self, cart_service_unit: CartService, mock_cart_orm: Cart
    ) -> None:
        """If the item doesn't exist in the cart, raise CartItemNotFoundError."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=mock_cart_orm)
        svc.repository.remove_item = AsyncMock(return_value=False)

        with pytest.raises(CartItemNotFoundError):
            await svc.remove_item_from_cart(TEST_USER_ID, TEST_CART_ITEM_ID)

    async def test_remove_item_from_cart_cart_not_found(
        self, cart_service_unit: CartService
    ) -> None:
        """If the user's cart doesn't exist, raise CartNotFoundError."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=None)

        with pytest.raises(CartNotFoundError):
            await svc.remove_item_from_cart(TEST_USER_ID, TEST_CART_ITEM_ID)


# ---------------------------------------------------------------------------
# clear_cart
# ---------------------------------------------------------------------------

class TestClearCart:
    async def test_clear_cart_success(
        self, cart_service_unit: CartService, mock_cart_orm: Cart
    ) -> None:
        """Clearing a cart calls the repository clear method."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=mock_cart_orm)
        svc.repository.clear_cart = AsyncMock(return_value=None)

        result = await svc.clear_cart(TEST_USER_ID)

        assert result is None
        svc.repository.clear_cart.assert_awaited_once_with(cart_id=TEST_CART_ID)

    async def test_clear_cart_missing_cart_is_noop(
        self, cart_service_unit: CartService
    ) -> None:
        """Clearing a non-existent cart is a no-op."""
        svc = cart_service_unit
        svc.repository.get_cart_by_user_id = AsyncMock(return_value=None)

        result = await svc.clear_cart(TEST_USER_ID)

        assert result is None
        svc.repository.clear_cart.assert_not_awaited()

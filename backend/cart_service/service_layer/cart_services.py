from uuid import UUID
from decimal import Decimal
from fastapi import status

from database_layer.cart_repository import CartRepository
from models.cart_models import Cart
from shared.schemas.cart_schemas import CartSchema, CartSummary, AddCartItem, UpdateCartItem, CartItemSchema
from shared.exceptions.base_exceptions import BaseAPIException


class CartNotFoundError(BaseAPIException):
    def __init__(self, user_id: UUID):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart for user {user_id} not found"
        )


class CartItemNotFoundError(BaseAPIException):
    def __init__(self, item_id: UUID):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart item {item_id} not found in cart"
        )


class CartService:
    def __init__(self, repository: CartRepository):
        self.repository = repository

    async def _get_or_create_cart_model(self, user_id: UUID) -> Cart:
        """Fetch the user's cart or create a new one if it doesn't exist."""
        cart = await self.repository.get_cart_by_user_id(user_id)
        if cart is not None:
            return cart

        new_cart = Cart(user_id=user_id)
        await self.repository.create(new_cart)

        cart = await self.repository.get_cart_by_user_id(user_id)
        if cart is None:
            raise CartNotFoundError(user_id)
        return cart

    async def get_or_create_cart(self, user_id: UUID) -> CartSchema:
        cart = await self._get_or_create_cart_model(user_id)
        return CartSchema.model_validate(cart)

    async def get_cart_summary(self, user_id: UUID) -> CartSummary:
        cart = await self._get_or_create_cart_model(user_id)

        total_items = sum(item.quantity for item in cart.items)
        total_amount = sum(
            (Decimal(item.quantity) * item.price_snapshot for item in cart.items),
            Decimal(0),
        )

        return CartSummary(
            id=cart.id,
            user_id=cart.user_id,
            total_items=total_items,
            total_amount=total_amount,
            items=[CartItemSchema.model_validate(item) for item in cart.items],
        )

    async def add_item_to_cart(self, user_id: UUID, item_data: AddCartItem) -> CartSchema:
        cart = await self._get_or_create_cart_model(user_id)

        await self.repository.add_item_to_cart(
            cart_id=cart.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            price_snapshot=item_data.price_snapshot
        )
        updated_cart = await self.repository.get_cart_by_user_id(user_id)
        if updated_cart is None:
            raise CartNotFoundError(user_id)
        return CartSchema.model_validate(updated_cart)

    async def update_item_quantity(self, user_id: UUID, item_id: UUID, item_data: UpdateCartItem) -> CartSchema:
        cart = await self.repository.get_cart_by_user_id(user_id)
        if cart is None:
            raise CartNotFoundError(user_id)

        item = await self.repository.update_item_quantity(cart_id=cart.id, item_id=item_id, quantity=item_data.quantity)
        if not item:
            raise CartItemNotFoundError(item_id)

        updated_cart = await self.repository.get_cart_by_user_id(user_id)
        if updated_cart is None:
            raise CartNotFoundError(user_id)
        return CartSchema.model_validate(updated_cart)

    async def remove_item_from_cart(self, user_id: UUID, item_id: UUID) -> CartSchema:
        cart = await self.repository.get_cart_by_user_id(user_id)
        if cart is None:
            raise CartNotFoundError(user_id)

        success = await self.repository.remove_item(cart_id=cart.id, item_id=item_id)
        if not success:
            raise CartItemNotFoundError(item_id)

        updated_cart = await self.repository.get_cart_by_user_id(user_id)
        if updated_cart is None:
            raise CartNotFoundError(user_id)
        return CartSchema.model_validate(updated_cart)

    async def clear_cart(self, user_id: UUID) -> None:
        cart = await self.repository.get_cart_by_user_id(user_id)
        if cart:
            await self.repository.clear_cart(cart_id=cart.id)

from uuid import UUID

from database_layer.cart_repository import CartRepository
from models.cart_models import Cart
from shared.schemas.cart_schemas import CartSchema, CartSummary, AddCartItem, UpdateCartItem
from exceptions.cart_exceptions import CartNotFoundError, CartItemNotFoundError





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
        return CartSummary.model_validate(cart)

    async def add_item_to_cart(self, user_id: UUID, item_data: AddCartItem) -> CartSchema:
        cart = await self._get_or_create_cart_model(user_id)

        await self.repository.add_item_to_cart(
            cart_id=cart.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            price_snapshot=item_data.price_snapshot
        )
        await self.repository.session.refresh(cart)
        return CartSchema.model_validate(cart)

    async def update_item_quantity(self, user_id: UUID, item_id: UUID, item_data: UpdateCartItem) -> CartSchema:
        cart = await self.repository.get_cart_by_user_id(user_id)
        if cart is None:
            raise CartNotFoundError(user_id)

        item = await self.repository.update_item_quantity(cart_id=cart.id, item_id=item_id, quantity=item_data.quantity)
        if not item:
            raise CartItemNotFoundError(item_id)

        await self.repository.session.refresh(cart)
        return CartSchema.model_validate(cart)

    async def remove_item_from_cart(self, user_id: UUID, item_id: UUID) -> CartSchema:
        cart = await self.repository.get_cart_by_user_id(user_id)
        if cart is None:
            raise CartNotFoundError(user_id)

        success = await self.repository.remove_item(cart_id=cart.id, item_id=item_id)
        if not success:
            raise CartItemNotFoundError(item_id)

        await self.repository.session.refresh(cart)
        return CartSchema.model_validate(cart)

    async def clear_cart(self, user_id: UUID) -> None:
        cart = await self.repository.get_cart_by_user_id(user_id)
        if cart:
            await self.repository.clear_cart(cart_id=cart.id)

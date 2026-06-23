from uuid import UUID
from fastapi import APIRouter, status, Request

from shared.schemas.cart_schemas import CartSchema, CartSummary, AddCartItem, UpdateCartItem
from dependencies.dependencies import cart_service_dependency

cart_routes = APIRouter(
    tags=["cart"]
)

@cart_routes.get("/users/{user_id}/cart",
                 response_model=CartSchema,
                 status_code=status.HTTP_200_OK)
async def get_cart(request: Request, user_id: UUID, cart_service: cart_service_dependency) -> CartSchema:
    """Get the cart for a user. Creates a new one if it doesn't exist."""
    return await cart_service.get_or_create_cart(user_id=user_id)


@cart_routes.get("/users/{user_id}/cart/summary",
                 response_model=CartSummary,
                 status_code=status.HTTP_200_OK)
async def get_cart_summary(request: Request, user_id: UUID, cart_service: cart_service_dependency) -> CartSummary:
    """Get a summary of the user's cart including total items and amount."""
    return await cart_service.get_cart_summary(user_id=user_id)


@cart_routes.post("/users/{user_id}/cart/items",
                  response_model=CartSchema,
                  status_code=status.HTTP_200_OK)
async def add_item_to_cart(request: Request, user_id: UUID, item_data: AddCartItem, cart_service: cart_service_dependency) -> CartSchema:
    """Add a new item to the cart or increase its quantity if it already exists."""
    return await cart_service.add_item_to_cart(user_id=user_id, item_data=item_data)


@cart_routes.put("/users/{user_id}/cart/items/{item_id}",
                 response_model=CartSchema,
                 status_code=status.HTTP_200_OK)
async def update_cart_item(request: Request, user_id: UUID, item_id: UUID, item_data: UpdateCartItem, cart_service: cart_service_dependency) -> CartSchema:
    """Update the quantity of an item in the cart."""
    return await cart_service.update_item_quantity(user_id=user_id, item_id=item_id, item_data=item_data)


@cart_routes.delete("/users/{user_id}/cart/items/{item_id}",
                    response_model=CartSchema,
                    status_code=status.HTTP_200_OK)
async def remove_cart_item(request: Request, user_id: UUID, item_id: UUID, cart_service: cart_service_dependency) -> CartSchema:
    """Remove an item from the cart completely."""
    return await cart_service.remove_item_from_cart(user_id=user_id, item_id=item_id)


@cart_routes.delete("/users/{user_id}/cart",
                    status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(request: Request, user_id: UUID, cart_service: cart_service_dependency) -> None:
    """Remove all items from the cart."""
    await cart_service.clear_cart(user_id=user_id)
    return None

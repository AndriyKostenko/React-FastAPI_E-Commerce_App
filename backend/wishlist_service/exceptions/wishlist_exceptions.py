from uuid import UUID

from fastapi import status

from shared.exceptions.base_exceptions import BaseAPIException


class WishlistNotFoundError(BaseAPIException):
    def __init__(self, user_id: UUID):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wishlist for user {user_id} not found"
        )


class WishlistItemNotFoundError(BaseAPIException):
    def __init__(self, item_id: UUID):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wishlist item {item_id} not found"
        )


class ProductNotFoundError(BaseAPIException):
    def __init__(self, product_id: UUID):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )


class DuplicateWishlistItemError(BaseAPIException):
    def __init__(self, product_id: UUID):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product {product_id} is already in the wishlist"
        )

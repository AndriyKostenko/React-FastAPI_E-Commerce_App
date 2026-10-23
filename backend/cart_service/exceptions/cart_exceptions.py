from uuid import UUID

from fastapi import status

from infrastructure.exceptions.base_exceptions import BaseAPIException




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


class CartLineQuantityLimitError(BaseAPIException):
    def __init__(self, limit: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A cart can hold at most {limit} of one item"
        )


class CartFullError(BaseAPIException):
    def __init__(self, limit: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A cart can hold up to {limit} different items; remove one first"
        )



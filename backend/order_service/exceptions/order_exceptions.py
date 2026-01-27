from uuid import UUID

from shared.base_exceptions import BaseAPIException

class OrderNotFoundError(BaseAPIException):
    """Exception raised when an order is not found in the database."""
    def __init__(self, order_id: UUID) -> None:
        super().__init__(
            status_code=404,
            detail=f"Order with ID: {order_id} is not found."
        )

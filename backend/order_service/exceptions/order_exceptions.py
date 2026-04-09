from uuid import UUID

from shared.base_exceptions import BaseAPIException

class OrderNotFoundError(BaseAPIException):
    """Exception raised when an order is not found in the database."""
    def __init__(self, order_id: UUID) -> None:
        super().__init__(
            status_code=404,
            detail=f"Order with ID: {order_id} is not found."
        )

class OrdersNotFoundError(BaseAPIException):
    """Exception raised when an orders are not found in the database."""
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Orders are not found."
        )

class DuplicatePaymentIntentError(BaseAPIException):
    """Exception raised when an order with the same payment_intent_id already exists."""
    def __init__(self, payment_intent_id: str) -> None:
        super().__init__(
            status_code=409,
            detail=f"Order with payment_intent_id '{payment_intent_id}' already exists."
        )

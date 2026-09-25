from uuid import UUID

from shared.exceptions.base_exceptions import BaseAPIException

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


class OrderNotCancellableError(BaseAPIException):
    """Exception raised when an order cannot be cancelled due to its current status."""
    def __init__(self, order_id, current_status: str) -> None:
        super().__init__(
            status_code=409,
            detail=f"Order {order_id} cannot be cancelled — current status: '{current_status}'."
        )


class OrderRefundNotAllowedError(BaseAPIException):
    """The order is not in a state that can be partly refunded."""
    def __init__(self, order_id, reason: str) -> None:
        super().__init__(status_code=409, detail=f"Order {order_id} cannot be refunded: {reason}")


class InvalidOrderRefundError(BaseAPIException):
    """The requested lines, quantities or amount are not refundable."""
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=422, detail=detail)

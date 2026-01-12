from shared.base_exceptions import BaseAPIException

class OrderNotFoundException(BaseAPIException):
    """Exception raised when an order is not found in the database."""
    def __init__(self, order_id: int) -> None:
        super().__init__(
            status_code=404,
            detail=f"Order with ID {order_id} not found."
        )

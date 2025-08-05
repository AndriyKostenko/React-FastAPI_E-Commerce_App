from errors.base import BaseAPIException

class ProductImageNotFoundError(BaseAPIException):
    """Exception raised when a product image is not found."""
    def __init__(self, message: str):
        super().__init__(status_code=404, detail=message)
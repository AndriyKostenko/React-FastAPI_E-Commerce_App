class ProductServiceError(Exception):
    """Base exception for all product-related errors."""
    def __init__(self, message: str):
        super().__init__(message)


class ProductCreationError(ProductServiceError):
    """Raised when product creation fails."""
    pass

class ProductNotFoundError(ProductServiceError):
    """Raised when a product is not found."""
    pass

class ProductUpdateError(ProductServiceError):
    """Raised when updating a product fails."""
    pass

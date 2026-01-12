from shared.base_exceptions import BaseAPIException  # type: ignore


class ProductImageNotFoundError(BaseAPIException):
    """Exception raised when a product image is not found."""

    def __init__(self, message: str):
        super().__init__(status_code=404, detail=message)


class ProductImageAlreadyExistsError(BaseAPIException):
    """Exception raised when a product image already exists."""

    def __init__(self, message: str):
        super().__init__(status_code=400, detail=message)


class ProductImageProcessingError(BaseAPIException):
    """Exception raised for errors during product image processing."""

    def __init__(self, message: str):
        super().__init__(status_code=400, detail=message)

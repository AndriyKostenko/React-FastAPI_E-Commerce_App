from shared.exceptions.base_exceptions import BaseAPIException


class CJOrderCreationError(BaseAPIException):
    """Raised when CJ order creation fails after retries."""
    def __init__(self, detail: str = "Order creation failed after retries."):
        super().__init__(status_code=500, detail=detail)


class CJProductMappingError(BaseAPIException):
    """Raised when a local product/variant cannot be mapped to CJ IDs."""
    def __init__(self, detail: str = "Product mapping failed."):
        super().__init__(status_code=500, detail=detail)


class CJOrderConfigurationError(BaseAPIException):
    """Raised when required CJ order settings or address fields are missing."""
    def __init__(self, detail: str = "Order configuration error."):
        super().__init__(status_code=500, detail=detail)


class ProviderNotFoundError(BaseAPIException):
    """Raised when the provider is not found."""
    def __init__(self, detail: str = "Provider not found."):
        super().__init__(status_code=404, detail=detail)


class SyncAlreadyInProgressError(BaseAPIException):
    """Raised when a sync process is already running for the supplier."""
    def __init__(self, detail: str = "Sync already in progress for supplier."):
        super().__init__(status_code=409, detail=detail)


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


class CJAddressValidationError(CJOrderConfigurationError):
    """Raised when a shipping address cannot be shipped by CJ.

    A subclass of CJOrderConfigurationError so the consumer keeps treating it as
    a definitive, pre-submission failure that the order saga can compensate.
    """
    def __init__(self, detail: str = "Shipping address is invalid."):
        super().__init__(detail=detail)
        self.status_code = 422


class CJOrderRejectedError(BaseAPIException):
    """Raised when CJ cancels or rejects an order it had already accepted."""
    def __init__(self, detail: str = "CJ rejected the order."):
        super().__init__(status_code=502, detail=detail)


class CJFreightQuoteError(BaseAPIException):
    """Raised when CJ cannot price shipping for a destination and cart."""
    def __init__(self, detail: str = "No CJ shipping options are available."):
        super().__init__(status_code=422, detail=detail)


class CJOrderAmbiguousError(Exception):
    """CJ may have accepted the order, so automatic compensation is unsafe."""



class ProviderNotFoundError(BaseAPIException):
    """Raised when the provider is not found."""
    def __init__(self, detail: str = "Provider not found."):
        super().__init__(status_code=404, detail=detail)


class SyncAlreadyInProgressError(BaseAPIException):
    """Raised when a sync process is already running for the supplier."""
    def __init__(self, detail: str = "Sync already in progress for supplier."):
        super().__init__(status_code=409, detail=detail)


class SupplierSyncConfigurationError(BaseAPIException):
    """Raised when a supplier sync policy is incomplete or unsafe."""

    def __init__(self, detail: str = "Supplier sync configuration is invalid."):
        super().__init__(status_code=422, detail=detail)

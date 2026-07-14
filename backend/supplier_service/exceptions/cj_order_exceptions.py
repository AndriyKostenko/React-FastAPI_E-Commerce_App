"""Exceptions for CJ Dropshipping order creation in supplier_service."""
from uuid import UUID


class CJOrderCreationError(Exception):
    """Raised when CJ order creation fails after retries."""
    pass


class CJProductMappingError(Exception):
    """Raised when a local product/variant cannot be mapped to CJ IDs."""
    pass


class CJOrderConfigurationError(Exception):
    """Raised when required CJ order settings or address fields are missing."""
    pass

"""Re-export the shared CJ Dropshipping API client for backwards compatibility."""
from shared.integrations.cj_api_client import (
    CJDropshippingAPIClient,
    CJDropshippingAPIError,
)

__all__ = ["CJDropshippingAPIClient", "CJDropshippingAPIError"]

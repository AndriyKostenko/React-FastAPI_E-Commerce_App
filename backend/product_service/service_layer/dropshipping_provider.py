from typing import Any, override

from interfaces.supplier_provider import SupplierProvider
from service_layer.cj_api_client import CJDropshippingAPIClient
from shared.schemas.dropshipping_schemas import CJProductsFilterParams
from shared.settings import Settings
from shared.utils.cj_filter_parser import CJFilterParser


class CJDropshippingProductProviderService(SupplierProvider):
    """High-level CJ Dropshipping product provider.

    Delegates HTTP transport and authentication to CJDropshippingAPIClient
    and focuses on product-specific operations.

    Common product endpoints:
        - GET /product/getCategory
        - GET /product/list
        - GET /product/listV2
        - GET /product/query
        - GET /product/stock/getInventoryByPid
    """

    def __init__(self, settings_instance: Settings) -> None:
        self.settings: Settings = settings_instance
        self.api_client: CJDropshippingAPIClient = CJDropshippingAPIClient(settings_instance)
        self.filter_parser: CJFilterParser = CJFilterParser()

    @override
    async def search_products(self, filters_query: CJProductsFilterParams) -> dict[str, Any]:
        """Search products using the V2 product list endpoint."""
        access_token = await self.api_client.ensure_access_token()
        params = self.filter_parser.parse_filter_params(filter_query=filters_query)

        url = self.api_client.build_url(self.settings.CJ_DROPSHIPPING_PRODUCT_LIST_URL, params)
        return await self.api_client._request("GET", url, access_token=access_token)

    @override
    async def get_product_details(self, pid: str) -> dict[str, Any]:
        """Fetch product details by pid."""
        access_token = await self.api_client.ensure_access_token()
        url = self.api_client.build_url(
            self.settings.CJ_DROPSHIPPING_PRODUCT_INFO_URL, {"pid": pid}
        )
        return await self.api_client._request("GET", url, access_token=access_token)

    @override
    async def get_inventory(self, pid: str) -> dict[str, Any]:
        """Fetch inventory for a product by its CJ product ID."""
        access_token = await self.api_client.ensure_access_token()
        base_url = str(self.settings.CJ_DROPSHIPPING_BASE_URL).rstrip("/")
        url = self.api_client.build_url(
            f"{base_url}/product/stock/getInventoryByPid", {"pid": pid}
        )
        return await self.api_client._request("GET", url, access_token=access_token)

    @override
    async def create_order(self, **kwargs: Any) -> dict[str, Any]:
        """Create a CJ order."""
        raise NotImplementedError(
            "CJ order creation is not implemented yet. "
            "Use the shopping/order/createOrder endpoint with the appropriate payload."
        )

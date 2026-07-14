from typing import Any

from shared.integrations.cj_api_client import CJDropshippingAPIClient
from service_layer.cj_filter_parser import CJFilterParser
from service_layer.cj_to_supplier_mapper import CJToSupplierMapper
from service_layer.supplier_provider import SupplierProvider
from shared.schemas.dropshipping_schemas import CJProductsFilterParams
from shared.schemas.supplier_schemas import GenericSupplierProduct, SupplierProductsPage
from shared.settings import Settings


class CJDropshippingProductProvider(SupplierProvider):
    """CJ Dropshipping provider that returns generic supplier product schemas."""

    def __init__(self, settings_instance: Settings) -> None:
        self.settings: Settings = settings_instance
        self.api_client: CJDropshippingAPIClient = CJDropshippingAPIClient(settings_instance)
        self.filter_parser: CJFilterParser = CJFilterParser()
        self.mapper: CJToSupplierMapper = CJToSupplierMapper()

    @property
    def supplier_id(self) -> str:
        return "cjdropshipping"

    async def search_products(self, filters_query: CJProductsFilterParams) -> SupplierProductsPage:
        """Search products using the V2 product list endpoint."""
        access_token = await self.api_client.ensure_access_token()
        params = self.filter_parser.parse_filter_params(filter_query=filters_query)
        url = self.api_client.build_url(self.settings.CJ_DROPSHIPPING_PRODUCT_LIST_URL, params)
        data = await self.api_client.request("GET", url, access_token=access_token)
        return self.mapper.map_products_page(
            data,
            page=filters_query.page,
            page_size=filters_query.size,
        )

    async def get_product_details(self, supplier_pid: str) -> dict[str, Any]:
        """Fetch raw product details by pid."""
        access_token = await self.api_client.ensure_access_token()
        url = self.api_client.build_url(self.settings.CJ_DROPSHIPPING_PRODUCT_INFO_URL, {"pid": supplier_pid})
        return await self.api_client.request("GET", url, access_token=access_token)

    async def get_mapped_product_details(self, supplier_pid: str) -> GenericSupplierProduct:
        """Fetch product details by pid and map to GenericSupplierProduct."""
        raw_details = await self.get_product_details(supplier_pid=supplier_pid)
        return self.mapper.map_product_details(raw_details)

    async def get_inventory(self, supplier_pid: str) -> dict[str, Any]:
        """Fetch inventory for a product by its CJ product ID."""
        access_token = await self.api_client.ensure_access_token()
        base_url = str(self.settings.CJ_DROPSHIPPING_BASE_URL).rstrip("/")
        url = self.api_client.build_url(f"{base_url}/product/stock/getInventoryByPid", {"pid": supplier_pid})
        return await self.api_client.request("GET", url, access_token=access_token)

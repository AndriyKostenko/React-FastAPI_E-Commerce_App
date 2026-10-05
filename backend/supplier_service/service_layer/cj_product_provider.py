from logging import Logger
from typing import Any

from service_layer.cj_api_client import CJDropshippingAPIClient
from service_layer.cj_inventory_verifier import CJDropshippingInventoryVerifier, StockVerificationResult
from service_layer.cj_to_supplier_mapper import CJToSupplierMapper
from service_layer.supplier_provider import SupplierProvider, WarehouseStock
from schemas.dropshipping_schemas import CJProductsFilterParams
from shared.contracts.shipping_region import CJ_WAREHOUSE_COUNTRY_CODE
from shared.contracts.supplier import GenericSupplierProduct
from schemas.supplier_schemas import SupplierProductsPage
from shared.settings import Settings


class CJDropshippingProductProvider(SupplierProvider):
    """CJ Dropshipping implementation of SupplierProvider.

    All collaborators are injected so they can be replaced in tests.
    When omitted, sensible defaults are constructed from ``settings``.
    """

    def __init__(
        self,
        settings: Settings,
        api_client: CJDropshippingAPIClient | None = None,
        mapper: CJToSupplierMapper | None = None,
        inventory_verifier: CJDropshippingInventoryVerifier | None = None,
        logger: Logger | None = None,
    ) -> None:
        self.settings: Settings = settings
        self.api_client: CJDropshippingAPIClient = api_client or CJDropshippingAPIClient(settings)
        self.mapper: CJToSupplierMapper = mapper or CJToSupplierMapper()
        self.inventory_verifier: CJDropshippingInventoryVerifier = (
            inventory_verifier or CJDropshippingInventoryVerifier(self.api_client, settings, logger)
        )
        self.logger: Logger | None = logger

    @property
    def supplier_id(self) -> str:
        return "cjdropshipping"
    
    async def search_products(self, filters_query: CJProductsFilterParams) -> SupplierProductsPage:
        """
        Search products using the V2 product list endpoint.

        Always limited to products with stock in CJ's China warehouses, whatever
        the caller asked for: this is the one door every listing, preview and
        sync goes through.
        """
        access_token = await self.api_client.ensure_access_token()
        filters_query = filters_query.model_copy(update={"countryCode": CJ_WAREHOUSE_COUNTRY_CODE})
        params = filters_query.model_dump(exclude_none=True)
        url = self.api_client.build_url(self.settings.CJ_DROPSHIPPING_PRODUCT_LIST_URL, params)
        data = await self.api_client.request("GET", url, access_token=access_token)
        return self.mapper.map_products_page(data, page=filters_query.page, page_size=filters_query.size)

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
        """Fetch raw inventory data for a product by its CJ product ID."""
        access_token = await self.api_client.ensure_access_token()
        url = self.api_client.build_url(self.settings.CJ_DROPSHIPPING_INVENTORY_URL, {"pid": supplier_pid})
        return await self.api_client.request("GET", url, access_token=access_token)

    async def get_warehouse_stock(self, supplier_pid: str) -> WarehouseStock:
        """Stock in CJ's China warehouses, in total and per variant."""
        return await self.inventory_verifier.fetch_warehouse_stock(supplier_pid)

    async def verify_stock(self, supplier_pid: str, requested_quantity: int) -> StockVerificationResult:
        """Verify that sufficient stock exists for ``requested_quantity`` units."""
        return await self.inventory_verifier.verify_product_stock(supplier_pid, requested_quantity)

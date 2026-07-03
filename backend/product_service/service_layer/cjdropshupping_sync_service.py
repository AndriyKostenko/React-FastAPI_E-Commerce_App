from service_layer.dropshipping_provider import CJDropshippingProductProviderService
from service_layer.product_service import ProductService
from shared.schemas.dropshipping_schemas import CJProductsFilterParams


class CJProductSyncService:
	"""Orchestrates pulling products from CJDropshppiing and saving them locally"""
	def __init__(self, 
				cj_provider: CJDropshippingProductProviderService, 
				product_service: ProductService) -> None:
		self.cj_provider: CJDropshippingProductProviderService = cj_provider
		self.product_service: ProductService = product_service

	async def run_product_synchronization(self, filters: CJProductsFilterParams) -> dict[str, int]:
		"""
		Fetches products from CJ and saves them to the database.
		"""
		results = {"inserted": 0, "skipped": 0, "failed": 0}
		cj_products = await self.cj_provider.search_products(filters)
		for product_data in cj_products:
			
from abc import ABC, abstractmethod
from typing import Any

from shared.schemas.product_schemas import CreateProduct

class SupplierProvider(ABC):
	@abstractmethod
	async def search_products(self, filters_query)-> list[CreateProduct]:
		...

	@abstractmethod
	async def get_product_details(self, pid: str) -> dict[str ,Any]:
		...

	@abstractmethod
	async def get_inventory(self, pid: str) -> dict[str ,Any]:
		...

	@abstractmethod
	async def create_order(self, *args, **kwargs) -> dict[str ,Any]:
		...

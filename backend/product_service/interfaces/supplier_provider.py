from abc import ABC, abstractmethod
from typing import Any

class SupplierProvider(ABC):
	@abstractmethod
	async def search_products(self, 
								keyword: str,
								page: int,
								size: int,
								category_id: str,
								**filters: dict[str, Any]) -> dict[str ,Any]:
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

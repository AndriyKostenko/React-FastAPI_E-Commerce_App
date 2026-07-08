from abc import ABC, abstractmethod
from typing import Any

from shared.schemas.dropshipping_schemas import CJProductsFilterParams
from shared.schemas.supplier_schemas import GenericSupplierProduct, SupplierProductsPage


class SupplierProvider(ABC):
    """Abstract interface for product supplier integrations.

    A SupplierProvider knows how to talk to one external supplier API and
    returns normalized ``GenericSupplierProduct`` objects.
    """

    @property
    @abstractmethod
    def supplier_id(self) -> str:
        """Stable identifier for this supplier, e.g. 'cjdropshipping'."""
        ...

    @abstractmethod
    async def search_products(self, filters_query: CJProductsFilterParams) -> SupplierProductsPage:
        """Search products from the supplier and return a normalized page."""
        ...

    @abstractmethod
    async def get_product_details(self, supplier_pid: str) -> dict[str, Any]:
        """Fetch raw product details by supplier pid."""
        ...

    @abstractmethod
    async def get_mapped_product_details(self, supplier_pid: str) -> GenericSupplierProduct:
        """Fetch product details and map to the generic supplier schema."""
        ...

    @abstractmethod
    async def get_inventory(self, supplier_pid: str) -> dict[str, Any]:
        """Fetch inventory information for a product."""
        ...

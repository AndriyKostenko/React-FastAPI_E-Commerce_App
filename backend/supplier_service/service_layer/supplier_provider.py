from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from schemas.dropshipping_schemas import CJProductsFilterParams
from shared.contracts.supplier import GenericSupplierProduct
from schemas.supplier_schemas import SupplierProductsPage


@dataclass(frozen=True)
class WarehouseStock:
    """A product's stock in the warehouses orders ship from: in total and per variant id."""
    total: int
    by_vid: dict[str, int]

    def sellable(self, vids: list[str], buffer: int) -> dict[str, int]:
        """
        What may be sold of each variant: its stock less the safety buffer.

        The buffer covers units sold here but not yet ordered from the
        supplier when this was measured. A variant the supplier did not
        report has nothing sellable.
        """
        held = max(0, buffer)
        return {vid: max(0, self.by_vid.get(vid, 0) - held) for vid in vids}


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

    @abstractmethod
    async def get_warehouse_stock(self, supplier_pid: str) -> WarehouseStock:
        """The product's stock in the warehouses orders ship from, per variant."""
        ...

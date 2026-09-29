"""Supplier stock in the catalogue: which products to ask about, and applying the answers."""

from dataclasses import dataclass

from database_layer.product_repository import ProductRepository
from shared.contracts.events import SupplierStockUpdatedEvent
from shared.contracts.supplier import SupplierStockKey, SupplierStockLevel
from models.product_models import Product


@dataclass(slots=True)
class StockApplyReport:
    updated: int = 0
    # An older measurement than the product already carries.
    stale: int = 0
    # A product the catalogue no longer has (deleted since it was asked about).
    unknown: int = 0


class SupplierStockService:
    """
    Keeps each supplier product's stock equal to what the supplier last reported.

    The levels are absolute and already reduced by the safety buffer, so they
    are written as they come: each listed variant's ``inventory_num``, the
    product's total ``quantity`` and ``in_stock``. A variant at zero stays
    listed but cannot be reserved.
    """

    def __init__(self, product_repository: ProductRepository) -> None:
        self._products = product_repository

    async def stock_keys(self, supplier_id: str) -> list[SupplierStockKey]:
        """Every product of ``supplier_id`` we sell, with its variant ids."""
        return [
            SupplierStockKey(supplier_pid=pid, vids=vids)
            for pid, vids in await self._products.list_supplier_stock_keys(supplier_id)
        ]

    async def apply(self, event: SupplierStockUpdatedEvent) -> StockApplyReport:
        report = StockApplyReport()
        for level in event.levels:
            product = await self._products.get_by_supplier_pid(
                event.supplier_id, level.supplier_pid, load_relations=["variants"]
            )
            if product is None:
                report.unknown += 1
                continue
            if product.stock_checked_at is not None and product.stock_checked_at >= event.measured_at:
                report.stale += 1
                continue
            self._write(product, level)
            product.stock_checked_at = event.measured_at
            report.updated += 1
        return report

    @staticmethod
    def _write(product: Product, level: SupplierStockLevel) -> None:
        for variant in product.variants:
            if variant.vid in level.variants:
                variant.inventory_num = level.variants[variant.vid]
        if product.variants:
            # What can actually be bought: only active variants count.
            quantity = sum(v.inventory_num or 0 for v in product.variants if v.active)
        else:
            quantity = sum(level.variants.values())
        product.quantity = quantity
        product.in_stock = quantity > 0

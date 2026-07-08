from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.product_models import Product
from shared.database_layer.database_layer import BaseRepository
from shared.database_layer.repository_mixins import AdvancedQueryMixin


class ProductRepository(AdvancedQueryMixin[Product], BaseRepository[Product]):
    """
    Repository for product-specific database operations.

    Extends BaseRepository with inventory-aware atomic updates and rich
    filtering/search that are only meaningful for the Product model.
    """

    # String fields that should use equality rather than ILIKE in get_all().
    EQUAL_ONLY_FIELDS: list[str] = ["id", "uuid"]

    def __init__(self, session: AsyncSession):
        super().__init__(session, Product)

    async def get_by_pid(self, pid: str, load_relations: list[str] | None = None) -> Product | None:
        """Get a product by its CJ Dropshipping pid."""
        query = select(Product).where(Product.pid == pid)
        if load_relations:
            from sqlalchemy.orm import selectinload
            for relation in load_relations:
                if hasattr(Product, relation):
                    query = query.options(selectinload(getattr(Product, relation)))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def atomic_decrement_quantity(self, item_id: UUID, requested: int) -> Product | None:
        """Atomically decrement `quantity` by *requested* only if sufficient stock exists.

        Issues a single ``UPDATE … WHERE quantity >= requested AND in_stock = TRUE``
        statement so the check and the decrement happen in one atomic DB operation.
        No separate SELECT is needed, which eliminates the TOCTOU race condition
        that arises from the classic read-check-write pattern.

        Returns the updated model instance on success, or ``None`` when the row
        was not found or did not have enough stock (0 rows affected).
        """
        stmt = (
            update(Product)
            .where(
                Product.id == item_id,
                Product.quantity >= requested,
                Product.in_stock.is_(True),
            )
            .values(
                quantity=Product.quantity - requested,
                in_stock=Product.quantity - requested > 0,
            )
            .returning(Product)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def atomic_increment_quantity(self, item_id: UUID, amount: int) -> Product | None:
        """Atomically increment ``quantity`` by *amount* and mark the product in-stock.

        Used for inventory release (SAGA compensation). Single UPDATE statement
        avoids the read-then-write race that ``release_inventory`` previously had.

        Returns the updated model instance, or ``None`` if the row was not found.
        """
        stmt = (
            update(Product)
            .where(Product.id == item_id)
            .values(
                quantity=Product.quantity + amount,
                in_stock=True,
            )
            .returning(Product)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

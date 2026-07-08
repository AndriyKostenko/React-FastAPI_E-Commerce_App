from sqlalchemy.ext.asyncio import AsyncSession

from shared.database_layer.database_layer import BaseRepository
from models.supplier_config_models import SupplierConfig


class SupplierConfigRepository(BaseRepository[SupplierConfig]):
    """Repository for supplier configuration CRUD operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SupplierConfig)

    async def get_by_supplier_id(self, supplier_id: str) -> SupplierConfig | None:
        return await self.get_by_field("supplier_id", supplier_id)

    async def get_active(self) -> list[SupplierConfig]:
        return await self.get_many_by_field("is_active", True)

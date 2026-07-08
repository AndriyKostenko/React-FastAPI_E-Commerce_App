from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database_layer.database_layer import BaseRepository
from models.supplier_sync_state_models import SupplierSyncState


class SupplierSyncStateRepository(BaseRepository[SupplierSyncState]):
    """Repository for supplier sync state tracking."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SupplierSyncState)

    async def get_latest_by_supplier_id(self, supplier_id: str) -> SupplierSyncState | None:
        results = await self.get_many_by_field("supplier_id", supplier_id, limit=1)
        return results[0] if results else None

    async def get_by_fetch_id(self, fetch_id: UUID) -> SupplierSyncState | None:
        return await self.get_by_field("fetch_id", fetch_id)

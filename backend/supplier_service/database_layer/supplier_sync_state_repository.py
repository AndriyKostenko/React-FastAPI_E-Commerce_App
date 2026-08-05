from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select

from shared.database_layer.database_layer import BaseRepository
from models.supplier_sync_state_models import SupplierSyncState


class SupplierSyncStateRepository(BaseRepository[SupplierSyncState]):
    """Repository for supplier sync state tracking."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SupplierSyncState)

    async def get_latest_by_supplier_id(self, supplier_id: str) -> SupplierSyncState | None:
        result = await self.session.execute(
            select(SupplierSyncState)
            .where(SupplierSyncState.supplier_id == supplier_id)
            .order_by(desc(SupplierSyncState.started_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_fetch_id(self, fetch_id: UUID) -> SupplierSyncState | None:
        return await self.get_by_field("fetch_id", fetch_id)

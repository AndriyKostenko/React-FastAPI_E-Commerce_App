from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.supplier_import_models import SupplierImportBatch
from shared.database_layer.database_layer import BaseRepository


class SupplierImportBatchRepository(BaseRepository[SupplierImportBatch]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SupplierImportBatch)

    async def get_by_event_id(self, event_id: UUID) -> SupplierImportBatch | None:
        return await self.get_by_field("event_id", event_id)

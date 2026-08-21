from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.inventory_reservation_models import InventoryReservation
from shared.database_layer.database_layer import BaseRepository


class InventoryReservationRepository(BaseRepository[InventoryReservation]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, InventoryReservation)

    async def get_order_for_update(self, order_id: UUID) -> list[InventoryReservation]:
        result = await self.session.execute(
            select(InventoryReservation)
            .where(InventoryReservation.order_id == order_id)
            .with_for_update()
        )
        return list(result.scalars().all())

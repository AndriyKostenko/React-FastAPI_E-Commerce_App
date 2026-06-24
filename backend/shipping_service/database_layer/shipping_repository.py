from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database_layer.database_layer import BaseRepository
from models.shipping_models import ShippingMethod, Shipment


class ShippingMethodRepository(BaseRepository[ShippingMethod]):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, model=ShippingMethod)

    async def get_active_methods(self) -> list[ShippingMethod]:
        """Return all active shipping methods ordered by base cost."""
        result = await self.session.execute(
            select(ShippingMethod)
            .where(ShippingMethod.is_active.is_(True))
            .order_by(ShippingMethod.base_cost.asc())
        )
        return list(result.scalars().all())


class ShipmentRepository(BaseRepository[Shipment]):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, model=Shipment)

    async def get_by_order_id(self, order_id: UUID) -> Shipment | None:
        """Return shipment for a specific order."""
        result = await self.session.execute(
            select(Shipment).where(Shipment.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tracking_number(self, tracking_number: str) -> Shipment | None:
        """Return shipment by tracking number."""
        result = await self.session.execute(
            select(Shipment).where(Shipment.tracking_number == tracking_number)
        )
        return result.scalar_one_or_none()

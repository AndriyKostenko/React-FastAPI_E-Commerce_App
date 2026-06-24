from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database_layer.shipping_repository import ShippingMethodRepository, ShipmentRepository
from service_layer.shipping_method_service import ShippingMethodService
from service_layer.shipment_service import ShipmentService
from shared.shared_instances import shipping_service_database_session_manager


async def get_db_session() -> AsyncSession:
    """Yield a database session managed by the shared session manager."""
    async with shipping_service_database_session_manager.transaction() as session:
        yield session


def get_shipping_method_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> ShippingMethodService:
    """Build the shipping method service with a fresh repository."""
    return ShippingMethodService(repository=ShippingMethodRepository(session=session))


def get_shipment_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> ShipmentService:
    """Build the shipment service with fresh repositories."""
    return ShipmentService(
        shipment_repository=ShipmentRepository(session=session),
        method_repository=ShippingMethodRepository(session=session),
    )


shipping_method_service_dependency = Annotated[ShippingMethodService, Depends(get_shipping_method_service)]
shipment_service_dependency = Annotated[ShipmentService, Depends(get_shipment_service)]

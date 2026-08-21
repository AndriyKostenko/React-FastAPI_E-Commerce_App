from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection
from sqlalchemy.ext.asyncio import AsyncSession

from database_layer.shipping_repository import ShippingMethodRepository, ShipmentRepository
from resources import ShippingApiResources, get_shipping_api_resources
from service_layer.shipping_method_service import ShippingMethodService
from service_layer.shipment_service import ShipmentService
from service_layer.outbox_event_service import OutboxEventService
from shared.database_layer.outbox_repository import OutboxRepository
from models.outbox_models import OutboxEvent



def get_resources(connection: HTTPConnection) -> ShippingApiResources:
    """Return resources owned by the current FastAPI lifespan."""
    return get_shipping_api_resources(connection)


resources_dependency = Annotated[ShippingApiResources, Depends(get_resources)]


async def get_db_session(
    resources: resources_dependency,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session managed by the shipping API lifespan."""
    async with resources.database.transaction() as session:
        yield session


def get_shipping_method_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> ShippingMethodService:
    """Build the shipping method service with a fresh repository."""
    return ShippingMethodService(repository=ShippingMethodRepository(session=session))


def get_shipment_service(
    resources: resources_dependency,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ShipmentService:
    """Build the shipment service with fresh repositories."""
    return ShipmentService(
        shipment_repository=ShipmentRepository(session=session),
        method_repository=ShippingMethodRepository(session=session),
        event_publisher=resources.event_publisher,
        outbox_event_service=OutboxEventService(
            OutboxRepository(session=session, model=OutboxEvent)
        ),
    )


shipping_method_service_dependency = Annotated[ShippingMethodService, Depends(get_shipping_method_service)]
shipment_service_dependency = Annotated[ShipmentService, Depends(get_shipment_service)]

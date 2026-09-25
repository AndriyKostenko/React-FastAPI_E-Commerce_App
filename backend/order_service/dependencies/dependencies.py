from typing import Annotated
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Request

from database_layer.order_address_repository import OrderAddressRepository
from database_layer.order_fulfillment_repository import (
    CustomProductionJobRepository,
    OrderLineFulfillmentRepository,
)
from database_layer.order_item_repository import OrderItemRepository
from shared.database_layer.outbox_repository import OutboxRepository
from service_layer.order_service import OrderService
from service_layer.order_item_service import OrderItemService
from service_layer.order_address_service import OrderAddressService
from service_layer.outbox_event_service import OutboxEventService
from service_layer.artwork_asset_client import ArtworkAssetClient
from service_layer.order_fulfillment_status_service import OrderFulfillmentStatusService
from service_layer.order_pricing_service import OrderPricingService
from service_layer.packing_slip_service import PackingSlipBuilder
from service_layer.production_queue_service import ProductionQueueService
from models.outbox_models import OutboxEvent
from database_layer.order_repository import OrderRepository
from config import settings
from resources import OrderApiResources, get_order_api_resources
from shared.utils.authenticated_caller import AuthenticatedCaller
from database_layer.order_refund_repository import OrderRefundRepository
from service_layer.order_refund_service import OrderRefundService
from database_layer.order_saga_repository import OrderSagaRepository


def get_api_resources(request: Request) -> OrderApiResources:
    """Return the resources owned by the active FastAPI lifespan."""
    return get_order_api_resources(request)


# Always depended on with scope="function": FastAPI's default runs a yield
# dependency's exit code after the response is sent, so the commit below ran
# after the client had been told "created" — a commit that then failed lost the
# write silently. Function scope commits before the response goes out.
async def get_db_session(
    resources: OrderApiResources = Depends(get_api_resources),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    FastAPI
     └─ get_db_session()
         └─ async with DatabaseSessionManager.transaction()
             └─ async with AsyncSession()
    """
    async with resources.database.transaction() as session:
        yield session

def get_order_item_service(session: AsyncSession = Depends(get_db_session, scope="function")) -> OrderItemService:
    """
    Dependency to provide an OrderItemService(for buisiness logic and data validation),
    which operates OrderItemRepository(inherits BaseRepository) for db session management.
    """
    return OrderItemService(repository=OrderItemRepository(session=session))

def get_order_address_service(session: AsyncSession = Depends(get_db_session, scope="function")) -> OrderAddressService:
    """
    Dependency to provide OrderAdressService (for buisiness logic and data validation),
    which operates OrderAddressRepository(inherits BaseRepository) for db session management.
    """
    return OrderAddressService(repository=OrderAddressRepository(session=session))

def get_outbox_service(session: AsyncSession = Depends(get_db_session, scope="function")) -> OutboxEventService:
    """
    Dependency to provide OutboxEventService (for buisiness logic and data validation),
    which operates OutboxRepository(inherits BaseRepository) for db session management.
    """
    return OutboxEventService(repository=OutboxRepository(session=session, model=OutboxEvent))

def get_order_service(resources: OrderApiResources = Depends(get_api_resources),
                      session: AsyncSession = Depends(get_db_session, scope="function"),
                      order_item_service: OrderItemService = Depends(get_order_item_service),
                      order_address_service: OrderAddressService = Depends(get_order_address_service),
                      outbox_event_service: OutboxEventService = Depends(get_outbox_service)) -> OrderService:
    """
    Dependency to provide OrderService (for buisiness logic and data validation),
    which operates OrderRepository(inherits BaseRepository) for db session management.
    """
    return OrderService(repository=OrderRepository(session=session),
                        outbox_event_service=outbox_event_service,
                        order_item_service=order_item_service,
                        order_address_service=order_address_service,
                        pricing_service=OrderPricingService(
                            settings=resources.settings,
                            catalog_client=resources.catalog_client,
                            freight_client=resources.freight_client,
                        ))

def get_fulfillment_status_service(
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> OrderFulfillmentStatusService:
    """
    Dependency to provide OrderFulfillmentStatusService, which records per-line
    fulfillment progress and re-derives the order-level delivery status from it.
    """
    return OrderFulfillmentStatusService(
        order_repository=OrderRepository(session=session),
        fulfillment_repository=OrderLineFulfillmentRepository(session=session),
    )


def get_production_queue_service(
    resources: OrderApiResources = Depends(get_api_resources),
    session: AsyncSession = Depends(get_db_session, scope="function"),
    fulfillment_status_service: OrderFulfillmentStatusService = Depends(
        get_fulfillment_status_service
    ),
    outbox_event_service: OutboxEventService = Depends(get_outbox_service),
) -> ProductionQueueService:
    """
    Dependency to provide ProductionQueueService, which drives one in-house
    print job from a queued garment to a delivered parcel.
    """
    return ProductionQueueService(
        repository=CustomProductionJobRepository(session=session),
        fulfillment_status_service=fulfillment_status_service,
        outbox_event_service=outbox_event_service,
        packing_slip_builder=PackingSlipBuilder(settings=resources.settings),
        artwork_client=resources.artwork_client,
        refund_service=OrderRefundService(
            order_repository=OrderRepository(session=session),
            saga_repository=OrderSagaRepository(session),
            refund_repository=OrderRefundRepository(session),
            outbox_event_service=outbox_event_service,
        ),
    )


def get_admin_caller(request: Request) -> AuthenticatedCaller:
    """The asserted caller if they are an admin; 401/403 otherwise."""
    return AuthenticatedCaller.require_admin(request, settings.SECRET_ROLE)


order_address_dependency = Annotated[OrderAddressService, Depends(get_order_address_service)]
order_item_dependency = Annotated[OrderItemService, Depends(get_order_item_service)]
def get_order_refund_service(
    session: AsyncSession = Depends(get_db_session, scope="function"),
    outbox_event_service: OutboxEventService = Depends(get_outbox_service),
) -> OrderRefundService:
    return OrderRefundService(
        order_repository=OrderRepository(session=session),
        saga_repository=OrderSagaRepository(session),
        refund_repository=OrderRefundRepository(session),
        outbox_event_service=outbox_event_service,
    )


order_service_dependency = Annotated[OrderService, Depends(get_order_service)]
order_refund_service_dependency = Annotated[OrderRefundService, Depends(get_order_refund_service)]
production_queue_service_dependency = Annotated[ProductionQueueService, Depends(get_production_queue_service)]
fulfillment_status_dependency = Annotated[OrderFulfillmentStatusService, Depends(get_fulfillment_status_service)]
admin_caller_dependency = Annotated[AuthenticatedCaller, Depends(get_admin_caller)]

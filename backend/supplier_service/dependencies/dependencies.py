from typing import Annotated
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database_layer.supplier_config_repository import SupplierConfigRepository
from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from service_layer.cj_freight_service import CJFreightQuoteService
from service_layer.cj_product_provider import CJDropshippingProductProvider
from service_layer.outbox_event_service import OutboxEventService
from models.outbox_models import OutboxEvent
from service_layer.sync_orchestrator_service import SupplierSyncOrchestrator
from shared.database_layer.outbox_repository import OutboxRepository
from resources import SupplierApiResources, get_supplier_api_resources


def get_resources(request: Request) -> SupplierApiResources:
    return get_supplier_api_resources(request)


# Always depended on with scope="function": FastAPI's default runs a yield
# dependency's exit code after the response is sent, so the commit below ran
# after the client had been told "created" — a commit that then failed lost the
# write silently. Function scope commits before the response goes out.
async def get_db_session(
    resources: SupplierApiResources = Depends(get_resources),
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session for each request."""
    async with resources.database.transaction() as session:
        yield session


def get_supplier_config_repository(session: AsyncSession = Depends(get_db_session, scope="function")) -> SupplierConfigRepository:
    return SupplierConfigRepository(session=session)


def get_supplier_sync_state_repository(session: AsyncSession = Depends(get_db_session, scope="function")) -> SupplierSyncStateRepository:
    return SupplierSyncStateRepository(session=session)


def get_outbox_event_service(session: AsyncSession = Depends(get_db_session, scope="function")) -> OutboxEventService:
    return OutboxEventService(repository=OutboxRepository(session=session, model=OutboxEvent))


def get_cj_provider(
    resources: SupplierApiResources = Depends(get_resources),
) -> CJDropshippingProductProvider:
    """Provide a CJDropshippingProductProvider wired with production settings."""
    return CJDropshippingProductProvider(
        settings=resources.settings,
        api_client=resources.cj_api_client,
        logger=resources.logger,
    )


def get_sync_orchestrator(
    resources: SupplierApiResources = Depends(get_resources),
    config_repository: SupplierConfigRepository = Depends(get_supplier_config_repository),
    sync_state_repository: SupplierSyncStateRepository = Depends(get_supplier_sync_state_repository),
    outbox_event_service: OutboxEventService = Depends(get_outbox_event_service),
    cj_provider: CJDropshippingProductProvider = Depends(get_cj_provider),
) -> SupplierSyncOrchestrator:
    return SupplierSyncOrchestrator(
        settings=resources.settings,
        config_repository=config_repository,
        sync_state_repository=sync_state_repository,
        outbox_event_service=outbox_event_service,
        provider=cj_provider,
    )


def get_freight_quote_service(
    resources: SupplierApiResources = Depends(get_resources),
) -> CJFreightQuoteService:
    """Provide the checkout freight-quote service sharing the process cache."""
    return CJFreightQuoteService(
        api_client=resources.cj_api_client,
        product_service_client=resources.product_service_client,
        settings=resources.settings,
        logger=resources.logger,
        cache=resources.freight_cache,
    )


cj_provider_dependency = Annotated[CJDropshippingProductProvider, Depends(get_cj_provider)]
freight_quote_dependency = Annotated[CJFreightQuoteService, Depends(get_freight_quote_service)]
sync_orchestrator_dependency = Annotated[SupplierSyncOrchestrator, Depends(get_sync_orchestrator)]

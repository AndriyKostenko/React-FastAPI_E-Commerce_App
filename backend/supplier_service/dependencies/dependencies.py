from typing import Annotated
from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database_layer.supplier_config_repository import SupplierConfigRepository
from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from service_layer.outbox_event_service import OutboxEventService
from service_layer.sync_orchestrator_service import SupplierSyncOrchestrator
from shared.database_layer.outbox_repository import OutboxRepository
from shared.shared_instances import logger, settings, supplier_service_database_session_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session for each request."""
    async with supplier_service_database_session_manager.transaction() as session:
        yield session


def get_supplier_config_repository(session: AsyncSession = Depends(get_db_session)) -> SupplierConfigRepository:
    return SupplierConfigRepository(session=session)


def get_supplier_sync_state_repository(session: AsyncSession = Depends(get_db_session)) -> SupplierSyncStateRepository:
    return SupplierSyncStateRepository(session=session)


def get_outbox_event_service(session: AsyncSession = Depends(get_db_session)) -> OutboxEventService:
    return OutboxEventService(repository=OutboxRepository(session=session))


def get_sync_orchestrator(
    config_repository: SupplierConfigRepository = Depends(get_supplier_config_repository),
    sync_state_repository: SupplierSyncStateRepository = Depends(get_supplier_sync_state_repository),
    outbox_event_service: OutboxEventService = Depends(get_outbox_event_service),
) -> SupplierSyncOrchestrator:
    return SupplierSyncOrchestrator(
        settings=settings,
        config_repository=config_repository,
        sync_state_repository=sync_state_repository,
        outbox_event_service=outbox_event_service,
    )


sync_orchestrator_dependency = Annotated[SupplierSyncOrchestrator, Depends(get_sync_orchestrator)]

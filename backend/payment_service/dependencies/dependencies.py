from typing import Annotated
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from database_layer.payment_repository import PaymentRepository
from shared.database_layer.outbox_repository import OutboxRepository
from service_layer.payment_service import PaymentService
from service_layer.outbox_event_service import OutboxEventService
from shared.shared_instances import logger, payment_service_database_session_manager, settings


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional database session scoped to the current request."""
    async with payment_service_database_session_manager.transaction() as session:
        yield session


def get_outbox_service(session: AsyncSession = Depends(get_db_session)) -> OutboxEventService:
    """Create an instance of OutboxEventService with the current database session."""
    return OutboxEventService(repository=OutboxRepository(session=session))


def get_payment_service(session: AsyncSession = Depends(get_db_session),
                        outbox_event_service: OutboxEventService = Depends(get_outbox_service)) -> PaymentService:
    """Create an instance of PaymentService with the current database session and outbox event service."""
    return PaymentService(
        repository=PaymentRepository(session=session),
        outbox_event_service=outbox_event_service,
        settings=settings,
        logger=logger
    )


payment_service_dependency = Annotated[PaymentService, Depends(get_payment_service)]

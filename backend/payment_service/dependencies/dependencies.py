from typing import Annotated
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Request

from database_layer.payment_repository import PaymentRepository
from shared.database_layer.outbox_repository import OutboxRepository
from service_layer.payment_service import PaymentService
from service_layer.outbox_event_service import OutboxEventService
from models.outbox_models import OutboxEvent
from resources import PaymentApiResources, get_payment_api_resources
from shared.idempotency.idempotency_service import IdempotencyEventService


def get_api_resources(request: Request) -> PaymentApiResources:
    """Return the resources owned by the active FastAPI lifespan."""
    return get_payment_api_resources(request)


async def get_db_session(
    resources: PaymentApiResources = Depends(get_api_resources),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional database session scoped to the current request."""
    async with resources.database.transaction() as session:
        yield session


def get_idempotency_service(
    resources: PaymentApiResources = Depends(get_api_resources),
) -> IdempotencyEventService:
    return resources.idempotency


def get_outbox_service(session: AsyncSession = Depends(get_db_session)) -> OutboxEventService:
    """Create an instance of OutboxEventService with the current database session."""
    return OutboxEventService(repository=OutboxRepository(session=session, model=OutboxEvent))


def get_payment_service(session: AsyncSession = Depends(get_db_session),
                        outbox_event_service: OutboxEventService = Depends(get_outbox_service),
                        resources: PaymentApiResources = Depends(get_api_resources)) -> PaymentService:
    """Create an instance of PaymentService with the current database session and outbox event service."""
    return PaymentService(
        repository=PaymentRepository(session=session),
        outbox_event_service=outbox_event_service,
        settings=resources.settings,
        logger=resources.logger
    )


payment_service_dependency = Annotated[PaymentService, Depends(get_payment_service)]
idempotency_service_dependency = Annotated[IdempotencyEventService, Depends(get_idempotency_service)]

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
from database_layer.payment_repository import PaymentDisputeRepository
from service_layer.payment_dispute_service import PaymentDisputeService
from service_layer.tax_service import TaxCalculationService
from config import logger


def get_api_resources(request: Request) -> PaymentApiResources:
    """Return the resources owned by the active FastAPI lifespan."""
    return get_payment_api_resources(request)


# Always depended on with scope="function": FastAPI's default runs a yield
# dependency's exit code after the response is sent, so the commit below ran
# after the client had been told "created" — a commit that then failed lost the
# write silently. Function scope commits before the response goes out.
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


def get_outbox_service(session: AsyncSession = Depends(get_db_session, scope="function")) -> OutboxEventService:
    """Create an instance of OutboxEventService with the current database session."""
    return OutboxEventService(repository=OutboxRepository(session=session, model=OutboxEvent))


def get_payment_service(session: AsyncSession = Depends(get_db_session, scope="function"),
                        outbox_event_service: OutboxEventService = Depends(get_outbox_service),
                        resources: PaymentApiResources = Depends(get_api_resources)) -> PaymentService:
    """Create an instance of PaymentService with the current database session and outbox event service."""
    return PaymentService(
        repository=PaymentRepository(session=session),
        outbox_event_service=outbox_event_service,
        settings=resources.settings,
        logger=resources.logger,
        stripe_client=resources.stripe_client,
    )


payment_service_dependency = Annotated[PaymentService, Depends(get_payment_service)]


def get_payment_dispute_service(
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> PaymentDisputeService:
    return PaymentDisputeService(
        payment_repository=PaymentRepository(session=session),
        dispute_repository=PaymentDisputeRepository(session=session),
        outbox_event_service=OutboxEventService(repository=OutboxRepository(session=session, model=OutboxEvent)),
        logger=logger,
    )


payment_dispute_service_dependency = Annotated[PaymentDisputeService, Depends(get_payment_dispute_service)]
idempotency_service_dependency = Annotated[IdempotencyEventService, Depends(get_idempotency_service)]


def get_tax_calculation_service(
    resources: PaymentApiResources = Depends(get_api_resources),
) -> TaxCalculationService:
    return TaxCalculationService(stripe_client=resources.stripe_client, settings=resources.settings)


tax_calculation_service_dependency = Annotated[TaxCalculationService, Depends(get_tax_calculation_service)]

"""
Shared pytest fixtures for payment_service unit and integration tests.

All unit-test fixtures replace heavy external dependencies (DB, Stripe, Redis)
with mocks so the tests run without any live services.

Integration-test fixtures use the real PostgreSQL test database
(PAYMENT_SERVICE_TEST_DB) and truncate every table between tests.
Stripe API calls are patched at the service level in integration tests too.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime

import pytest
from fastapi import Depends
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from database_layer.payment_repository import PaymentRepository
from dependencies.dependencies import get_db_session, get_payment_service, get_outbox_service
from service_layer.payment_service import PaymentService
from service_layer.outbox_event_service import OutboxEventService
from shared.database_layer.outbox_repository import OutboxRepository
from shared.shared_instances import test_payment_service_database_session_manager
from shared.schemas.payment_schemas import PaymentSchema
from shared.enums.status_enums import PaymentStatus
from tests.constants import (
    TEST_PAYMENT_ID,
    TEST_ORDER_ID,
    TEST_USER_ID,
    TEST_STRIPE_INTENT_ID,
    TEST_CLIENT_SECRET,
    TEST_DATETIME,
    TEST_EMAIL,
    TEST_AMOUNT,
    TEST_CURRENCY,
    TEST_API,
    MOCK_PAYMENT_INTENT_RESULT,
)


# ---------------------------------------------------------------------------
# ORM mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_payment_orm() -> MagicMock:
    """Fake SQLAlchemy Payment ORM object with all required attributes."""
    payment = MagicMock()
    payment.id = TEST_PAYMENT_ID
    payment.order_id = TEST_ORDER_ID
    payment.user_id = TEST_USER_ID
    payment.user_email = TEST_EMAIL
    payment.stripe_payment_intent_id = TEST_STRIPE_INTENT_ID
    payment.amount = TEST_AMOUNT
    payment.currency = TEST_CURRENCY
    payment.status = PaymentStatus.PENDING
    payment.failure_reason = None
    payment.date_created = TEST_DATETIME
    payment.date_updated = None
    return payment


# ---------------------------------------------------------------------------
# Repository mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_payment_repository() -> MagicMock:
    """Mock PaymentRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_by_field = AsyncMock()
    repo.create = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update_by_id = AsyncMock()
    repo.delete_by_id = AsyncMock()
    repo.session = MagicMock()
    repo.session.begin_nested = MagicMock(return_value=_AsyncContextManagerMock())
    return repo


@pytest.fixture
def mock_outbox_repository() -> MagicMock:
    """Mock OutboxRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_many_by_field = AsyncMock()
    repo.update_by_id = AsyncMock()
    return repo


class _AsyncContextManagerMock:
    """Helper for mocking `async with repo.session.begin_nested()`."""
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Settings / Stripe mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock Settings object with Stripe-related attributes."""
    s = MagicMock()
    s.FULL_STRIPE_WEBHOOK_ENDPOINT = "https://example.com/api/v1/payments/webhook"
    s.STRIPE_WEBHOOK_SECRET = "whsec_test_secret"
    s.STRIPE_TEST_SECRET_KEY = "sk_test_fake_key"
    return s


@pytest.fixture
def mock_stripe_client() -> MagicMock:
    """Mock StripeClient — synchronous methods (Stripe SDK is sync)."""
    stripe = MagicMock()

    def _make_intent(*args, **kwargs) -> MagicMock:
        m = MagicMock()
        m.id = f"pi_test_{uuid4().hex[:12]}"
        m.client_secret = TEST_CLIENT_SECRET
        return m

    # payment intents
    intent_mock = MagicMock()
    intent_mock.id = TEST_STRIPE_INTENT_ID
    intent_mock.client_secret = TEST_CLIENT_SECRET
    stripe.v1.payment_intents.create.side_effect = _make_intent
    stripe.v1.payment_intents.retrieve.return_value = intent_mock
    # refunds
    refund_mock = MagicMock()
    refund_mock.id = "re_test_refund123"
    stripe.v1.refunds.create.return_value = refund_mock
    return stripe


# ---------------------------------------------------------------------------
# Service fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_outbox_event_service(mock_outbox_repository: MagicMock) -> OutboxEventService:
    """OutboxEventService wired with a mocked repository."""
    return OutboxEventService(repository=mock_outbox_repository)


@pytest.fixture
def payment_service_unit(
    mock_payment_repository: MagicMock,
    mock_outbox_event_service: OutboxEventService,
    mock_settings: MagicMock,
    mock_stripe_client: MagicMock,
) -> PaymentService:
    """PaymentService wired with all mocked dependencies + mocked Stripe client."""
    svc = PaymentService(
        repository=mock_payment_repository,
        outbox_event_service=mock_outbox_event_service,
        settings=mock_settings,
        logger=MagicMock(),
    )
    svc._stripe = mock_stripe_client
    return svc


# ---------------------------------------------------------------------------
# Route-level fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_route_payment_service() -> MagicMock:
    """Full mock of PaymentService for app.dependency_overrides in route tests."""
    svc = MagicMock()
    svc.create_payment_intent = AsyncMock(return_value=MOCK_PAYMENT_INTENT_RESULT)
    svc.construct_webhook_event = AsyncMock()
    svc.handle_payment_intent_succeeded = AsyncMock(return_value=None)
    svc.handle_payment_intent_failed = AsyncMock(return_value=None)
    svc.handle_payment_intent_cancelled = AsyncMock(return_value=None)
    svc.handle_charge_refund_updated = AsyncMock(return_value=None)
    svc.get_payment_by_id = AsyncMock()
    svc.get_payments = AsyncMock()
    return svc


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan replaces the real one to avoid DB/Redis/RabbitMQ connections."""
    yield


@pytest.fixture
async def client_for_unit_testing(
    mock_route_payment_service: MagicMock,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP test client for route-level unit tests.

    - Replaces the FastAPI lifespan with a no-op.
    - Overrides the payment service dependency.
    - Patches idempotency_service in the routes module so Redis is not needed.
    """
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_payment_service] = lambda: mock_route_payment_service

    mock_idempotency = MagicMock()
    mock_idempotency.try_claim_event = AsyncMock(return_value=True)
    mock_idempotency.mark_event_as_processed = AsyncMock(return_value=None)
    mock_idempotency.release_claim = AsyncMock(return_value=None)

    with patch("routes.payment_routes.idempotency_service", mock_idempotency):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_client:
            yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


# ---------------------------------------------------------------------------
# Integration-test fixtures  (real DB + real services, Stripe patched)
# ---------------------------------------------------------------------------

@pytest.fixture
async def integration_client() -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP client for integration tests.

    What is real:
      - PostgreSQL (payment_service TEST database)
      - PaymentService, OutboxEventService and all repositories

    What is mocked:
      - FastAPI lifespan (tables created directly)
      - Stripe API calls (patched on the service instance)
      - Redis idempotency service in the routes module

    Isolation:
      - Before yield: init schema (idempotent)
      - After  yield: TRUNCATE all tables
    """
    await test_payment_service_database_session_manager.init_db()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_payment_service_database_session_manager.transaction() as session:
            yield session

    def _override_get_outbox_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> OutboxEventService:
        return OutboxEventService(repository=OutboxRepository(session=session))

    def _override_get_payment_service(
        session: AsyncSession = Depends(_override_get_db_session),
        outbox_event_service: OutboxEventService = Depends(_override_get_outbox_service),
    ) -> PaymentService:
        from shared.shared_instances import settings, logger
        svc = PaymentService(
            repository=PaymentRepository(session=session),
            outbox_event_service=outbox_event_service,
            settings=settings,
            logger=logger,
        )
        # Patch the Stripe client so no real Stripe API calls are made
        def _make_intent(*args, **kwargs) -> MagicMock:
            m = MagicMock()
            m.id = f"pi_test_{uuid4().hex[:12]}"
            m.client_secret = TEST_CLIENT_SECRET
            return m

        stripe_mock = MagicMock()
        intent_mock = MagicMock()
        intent_mock.id = TEST_STRIPE_INTENT_ID
        intent_mock.client_secret = TEST_CLIENT_SECRET
        stripe_mock.v1.payment_intents.create.side_effect = _make_intent
        stripe_mock.v1.payment_intents.retrieve.return_value = intent_mock
        refund_mock = MagicMock()
        refund_mock.id = "re_test_refund123"
        stripe_mock.v1.refunds.create.return_value = refund_mock
        svc._stripe = stripe_mock
        return svc

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_outbox_service] = _override_get_outbox_service
    app.dependency_overrides[get_payment_service] = _override_get_payment_service

    mock_idempotency = MagicMock()
    mock_idempotency.try_claim_event = AsyncMock(return_value=True)
    mock_idempotency.mark_event_as_processed = AsyncMock(return_value=None)
    mock_idempotency.release_claim = AsyncMock(return_value=None)

    with patch("routes.payment_routes.idempotency_service", mock_idempotency):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_client:
            yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan

    await test_payment_service_database_session_manager.truncate_all_tables()

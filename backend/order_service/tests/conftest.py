"""
Shared pytest fixtures for order_service unit and integration tests.

Unit-test fixtures replace all external dependencies (DB, RabbitMQ, Redis)
with mocks so the tests run without any live services.

Integration-test fixtures use the real PostgreSQL test database
(ORDER_SERVICE_TEST_DB) and truncate all tables between tests.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import Depends
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from database_layer.order_repository import OrderRepository
from database_layer.order_item_repository import OrderItemRepository
from database_layer.order_address_repository import OrderAddressRepository
from dependencies.dependencies import (
    get_db_session,
    get_order_service,
    get_order_item_service,
    get_order_address_service,
    get_outbox_service,
)
from service_layer.order_service import OrderService
from service_layer.order_item_service import OrderItemService
from service_layer.order_address_service import OrderAddressService
from service_layer.outbox_event_service import OutboxEventService
from shared.database_layer.outbox_repository import OutboxRepository
from shared.shared_instances import settings, test_order_service_database_session_manager
from shared.enums.status_enums import OrderStatus, OrderDeliveryStatus
from tests.constants import (
    TEST_ORDER_ID,
    TEST_ORDER_ITEM_ID,
    TEST_ORDER_ADDRESS_ID,
    TEST_USER_ID,
    TEST_PRODUCT_ID,
    TEST_PAYMENT_INTENT_ID,
    TEST_DATETIME,
    TEST_EMAIL,
    TEST_AMOUNT,
    TEST_CURRENCY,
    MOCK_ORDER_RESULT,
)


from shared.testing.helpers import allow_testserver_host


# ---------------------------------------------------------------------------
# Host-validation bypass for ASGI test client
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _allow_testserver_host() -> None:
    """Make the default httpx/TestClient host ('testserver') pass host checks."""
    allow_testserver_host()


# ---------------------------------------------------------------------------
# Async context manager helper
# ---------------------------------------------------------------------------

class _AsyncContextManagerMock:
    """Helper for mocking `async with repo.session.begin_nested()`."""
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# ORM mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_order_orm() -> MagicMock:
    """Fake SQLAlchemy Order ORM object with all required attributes."""
    order = MagicMock()
    order.id = TEST_ORDER_ID
    order.user_id = TEST_USER_ID
    order.user_email = TEST_EMAIL
    order.amount = TEST_AMOUNT
    order.currency = TEST_CURRENCY
    order.status = OrderStatus.PENDING
    order.delivery_status = OrderDeliveryStatus.PENDING
    order.payment_intent_id = TEST_PAYMENT_INTENT_ID
    order.address_id = TEST_ORDER_ADDRESS_ID
    order.date_created = TEST_DATETIME
    order.date_updated = None
    return order


@pytest.fixture
def mock_order_item_orm() -> MagicMock:
    """Fake SQLAlchemy OrderItem ORM object."""
    item = MagicMock()
    item.id = TEST_ORDER_ITEM_ID
    item.order_id = TEST_ORDER_ID
    item.product_id = TEST_PRODUCT_ID
    item.quantity = 2
    item.price = 49.99
    return item


@pytest.fixture
def mock_order_address_orm() -> MagicMock:
    """Fake SQLAlchemy OrderAddress ORM object."""
    address = MagicMock()
    address.id = TEST_ORDER_ADDRESS_ID
    address.user_id = TEST_USER_ID
    address.street = "123 Test St"
    address.city = "Testville"
    address.province = "TS"
    address.postal_code = "T1T 1T1"
    return address


# ---------------------------------------------------------------------------
# Repository mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_order_repository() -> MagicMock:
    """Mock OrderRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_many_by_field = AsyncMock()
    repo.create = AsyncMock()
    repo.update_by_id = AsyncMock()
    repo.delete_by_id = AsyncMock()
    repo.session = MagicMock()
    repo.session.begin_nested = MagicMock(return_value=_AsyncContextManagerMock())
    return repo


@pytest.fixture
def mock_order_item_repository() -> MagicMock:
    """Mock OrderItemRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.create_many = AsyncMock()
    repo.get_many_by_field = AsyncMock()
    return repo


@pytest.fixture
def mock_order_address_repository() -> MagicMock:
    """Mock OrderAddressRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_outbox_repository() -> MagicMock:
    """Mock OutboxRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_many_by_field = AsyncMock()
    repo.update_by_id = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Service fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_outbox_event_service(mock_outbox_repository: MagicMock) -> OutboxEventService:
    """OutboxEventService wired with a mocked repository."""
    return OutboxEventService(repository=mock_outbox_repository)


@pytest.fixture
def mock_order_item_service(mock_order_item_repository: MagicMock) -> OrderItemService:
    """OrderItemService wired with a mocked repository."""
    return OrderItemService(repository=mock_order_item_repository)


@pytest.fixture
def mock_order_address_service(mock_order_address_repository: MagicMock) -> OrderAddressService:
    """OrderAddressService wired with a mocked repository."""
    return OrderAddressService(repository=mock_order_address_repository)


@pytest.fixture
def order_service_unit(
    mock_order_repository: MagicMock,
    mock_order_item_service: OrderItemService,
    mock_order_address_service: OrderAddressService,
    mock_outbox_event_service: OutboxEventService,
) -> OrderService:
    """OrderService wired with all mocked dependencies."""
    return OrderService(
        repository=mock_order_repository,
        order_item_service=mock_order_item_service,
        order_address_service=mock_order_address_service,
        outbox_event_service=mock_outbox_event_service,
    )


# ---------------------------------------------------------------------------
# Route-level fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_route_order_service() -> MagicMock:
    """Full mock of OrderService for app.dependency_overrides in route tests."""
    svc = MagicMock()
    svc.create_order = AsyncMock(return_value=MOCK_ORDER_RESULT)
    svc.get_orders = AsyncMock(return_value=[MOCK_ORDER_RESULT])
    svc.get_order_by_id = AsyncMock(return_value=MOCK_ORDER_RESULT)
    svc.get_orders_by_user_id = AsyncMock(return_value=[MOCK_ORDER_RESULT])
    svc.update_order = AsyncMock(return_value=MOCK_ORDER_RESULT)
    svc.cancel_order = AsyncMock(return_value=MOCK_ORDER_RESULT)
    svc.delete_order_by_id = AsyncMock(return_value=None)
    return svc


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan to avoid DB/Redis/RabbitMQ connections during tests."""
    yield


@pytest.fixture
async def client_for_unit_testing(
    mock_route_order_service: MagicMock,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP test client for route-level unit tests.
    Replaces the FastAPI lifespan with a no-op and overrides the order service.
    """
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_order_service] = lambda: mock_route_order_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


# ---------------------------------------------------------------------------
# Integration-test fixtures (real DB + real services)
# ---------------------------------------------------------------------------

@pytest.fixture
async def integration_client() -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP client for integration tests.

    What is real:
      - PostgreSQL (order_service TEST database)
      - OrderService, OrderItemService, OrderAddressService, OutboxEventService

    What is mocked:
      - FastAPI lifespan (tables created directly via init_db)

    Isolation:
      - Before yield: init schema (idempotent)
      - After  yield: TRUNCATE all tables
    """
    await test_order_service_database_session_manager.init_db()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_order_service_database_session_manager.transaction() as session:
            yield session

    def _override_get_order_item_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> OrderItemService:
        return OrderItemService(repository=OrderItemRepository(session=session))

    def _override_get_order_address_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> OrderAddressService:
        return OrderAddressService(repository=OrderAddressRepository(session=session))

    def _override_get_outbox_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> OutboxEventService:
        return OutboxEventService(repository=OutboxRepository(session=session))

    def _override_get_order_service(
        session: AsyncSession = Depends(_override_get_db_session),
        order_item_service: OrderItemService = Depends(_override_get_order_item_service),
        order_address_service: OrderAddressService = Depends(_override_get_order_address_service),
        outbox_event_service: OutboxEventService = Depends(_override_get_outbox_service),
    ) -> OrderService:
        return OrderService(
            repository=OrderRepository(session=session),
            order_item_service=order_item_service,
            order_address_service=order_address_service,
            outbox_event_service=outbox_event_service,
        )

    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_order_item_service] = _override_get_order_item_service
    app.dependency_overrides[get_order_address_service] = _override_get_order_address_service
    app.dependency_overrides[get_outbox_service] = _override_get_outbox_service
    app.dependency_overrides[get_order_service] = _override_get_order_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
    settings.DEBUG_MODE = original_debug_mode

    await test_order_service_database_session_manager.truncate_all_tables()

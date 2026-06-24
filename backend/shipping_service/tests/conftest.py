"""
Shared pytest fixtures for shipping_service unit and integration tests.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import Depends
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from database_layer.shipping_repository import ShippingMethodRepository, ShipmentRepository
from dependencies.dependencies import get_db_session, get_shipping_method_service, get_shipment_service
from models.shipping_models import ShippingMethod, Shipment
from service_layer.shipping_method_service import ShippingMethodService
from service_layer.shipment_service import ShipmentService
from shared.schemas.shipping_schemas import ShippingMethodSchema, ShipmentSchema
from shared.shared_instances import settings, test_shipping_service_database_session_manager
from shared.testing.helpers import allow_testserver_host
from shared.shared_instances import test_settings


@pytest.fixture(autouse=True)
def _allow_testserver_host() -> None:
    """Make the default httpx/TestClient host ('testserver') pass host checks."""
    allow_testserver_host()


def _make_shipping_method_orm(
    method_id: UUID = test_settings.TEST_SHIPPING_METHOD_ID,
    name: str = "Standard Shipping",
    carrier: str = "FedEx",
    base_cost: Decimal = Decimal("5.99"),
    estimated_days: int = 5,
    is_active: bool = True,
) -> ShippingMethod:
    method = ShippingMethod(
        name=name,
        carrier=carrier,
        base_cost=base_cost,
        estimated_days=estimated_days,
        is_active=is_active,
    )
    method.id = method_id
    method.date_created = test_settings.TEST_DATETIME
    method.date_updated = None
    return method


def _make_shipment_orm(
    shipment_id: UUID = test_settings.TEST_SHIPMENT_ID,
    order_id: UUID = test_settings.TEST_ORDER_ID,
    user_id: UUID = test_settings.TEST_USER_ID,
    method_id: UUID = test_settings.TEST_SHIPPING_METHOD_ID,
    status: str = "pending",
) -> Shipment:
    shipment = Shipment(
        order_id=order_id,
        user_id=user_id,
        method_id=method_id,
        status=status,
    )
    shipment.id = shipment_id
    shipment.date_created = test_settings.TEST_DATETIME
    shipment.date_updated = None
    return shipment


@pytest.fixture
def mock_shipping_method_orm() -> ShippingMethod:
    return _make_shipping_method_orm()


@pytest.fixture
def mock_shipment_orm(mock_shipping_method_orm: ShippingMethod) -> Shipment:
    shipment = _make_shipment_orm()
    shipment.method = mock_shipping_method_orm
    return shipment


@pytest.fixture
def mock_method_repository() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.get_active_methods = AsyncMock()
    repo.create = AsyncMock()
    repo.update_by_id = AsyncMock()
    repo.delete = AsyncMock()
    repo.session = MagicMock()
    return repo


@pytest.fixture
def mock_shipment_repository() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_order_id = AsyncMock()
    repo.create = AsyncMock()
    repo.update_by_id = AsyncMock()
    repo.session = MagicMock()
    return repo


@pytest.fixture
def shipping_method_service_unit(mock_method_repository: MagicMock) -> ShippingMethodService:
    return ShippingMethodService(repository=mock_method_repository)


@pytest.fixture
def shipment_service_unit(
    mock_shipment_repository: MagicMock,
    mock_method_repository: MagicMock,
) -> ShipmentService:
    return ShipmentService(
        shipment_repository=mock_shipment_repository,
        method_repository=mock_method_repository,
    )


@pytest.fixture
def mock_route_shipping_method_service() -> MagicMock:
    method_schema = ShippingMethodSchema(
        id=test_settings.TEST_SHIPPING_METHOD_ID,
        name="Standard Shipping",
        carrier="FedEx",
        base_cost=Decimal("5.99"),
        estimated_days=5,
        is_active=True,
        date_created=test_settings.TEST_DATETIME,
        date_updated=None,
    )

    svc = MagicMock()
    svc.list_active_methods = AsyncMock(return_value=[method_schema])
    svc.list_all_methods = AsyncMock(return_value=[method_schema])
    svc.get_method_by_id = AsyncMock(return_value=method_schema)
    svc.create_method = AsyncMock(return_value=method_schema)
    svc.update_method = AsyncMock(return_value=method_schema)
    svc.delete_method = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def mock_route_shipment_service() -> MagicMock:
    shipment_schema = ShipmentSchema(
        id=test_settings.TEST_SHIPMENT_ID,
        order_id=test_settings.TEST_ORDER_ID,
        user_id=test_settings.TEST_USER_ID,
        method_id=test_settings.TEST_SHIPPING_METHOD_ID,
        status="pending",
        date_created=test_settings.TEST_DATETIME,
        date_updated=None,
    )

    svc = MagicMock()
    svc.get_shipment_by_id = AsyncMock(return_value=shipment_schema)
    svc.get_shipment_by_order_id = AsyncMock(return_value=shipment_schema)
    svc.create_shipment = AsyncMock(return_value=shipment_schema)
    svc.update_shipment = AsyncMock(return_value=shipment_schema)
    svc.calculate_rate = AsyncMock(return_value={"rates": []})
    return svc


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan to avoid DB/Redis/RabbitMQ connections during tests."""
    yield


@pytest.fixture
async def client_for_unit_testing(
    mock_route_shipping_method_service: MagicMock,
    mock_route_shipment_service: MagicMock,
) -> AsyncGenerator[AsyncClient, Any]:
    """Async HTTP test client for route-level unit tests."""
    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_shipping_method_service] = lambda: mock_route_shipping_method_service
    app.dependency_overrides[get_shipment_service] = lambda: mock_route_shipment_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
    settings.DEBUG_MODE = original_debug_mode


@pytest.fixture
async def integration_client() -> AsyncGenerator[AsyncClient, Any]:
    """Async HTTP client for integration tests using the real test DB."""
    await test_shipping_service_database_session_manager.init_db()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_shipping_service_database_session_manager.transaction() as session:
            yield session

    def _override_get_shipping_method_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> ShippingMethodService:
        return ShippingMethodService(ShippingMethodRepository(session=session))

    def _override_get_shipment_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> ShipmentService:
        return ShipmentService(
            shipment_repository=ShipmentRepository(session=session),
            method_repository=ShippingMethodRepository(session=session),
        )

    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_shipping_method_service] = _override_get_shipping_method_service
    app.dependency_overrides[get_shipment_service] = _override_get_shipment_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
    settings.DEBUG_MODE = original_debug_mode

    await test_shipping_service_database_session_manager.truncate_all_tables()

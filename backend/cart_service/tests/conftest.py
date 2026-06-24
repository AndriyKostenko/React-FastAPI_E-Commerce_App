"""
Shared pytest fixtures for cart_service unit and integration tests.

Unit-test fixtures replace all external dependencies (DB, Redis, RabbitMQ)
with mocks so the tests run without any live services.

Integration-test fixtures use the real PostgreSQL test database
(CART_SERVICE_TEST_DB) and truncate all tables between tests.
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
from database_layer.cart_repository import CartRepository
from dependencies.dependencies import get_db_session, get_cart_service
from models.cart_models import Cart, CartItem
from service_layer.cart_services import CartService
from shared.schemas.cart_schemas import CartSchema, CartItemSchema, CartSummary
from shared.shared_instances import settings, test_cart_service_database_session_manager
from shared.testing.helpers import allow_testserver_host
from shared.shared_instances import test_settings


# ---------------------------------------------------------------------------
# Host-validation bypass for ASGI test client
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _allow_testserver_host() -> None:
    """Make the default httpx/TestClient host ('testserver') pass host checks."""
    allow_testserver_host()


# ---------------------------------------------------------------------------
# ORM model fixtures
# ---------------------------------------------------------------------------

def _make_cart_item_orm(
    item_id: UUID = test_settings.TEST_CART_ITEM_ID,
    cart_id: UUID = test_settings.TEST_CART_ID,
    product_id: UUID = test_settings.TEST_PRODUCT_ID,
    quantity: int = 2,
    price_snapshot: Decimal = test_settings.TEST_CART_PRICE_SNAPSHOT,
) -> CartItem:
    """Build a real CartItem model instance for use in unit tests."""
    item = CartItem(
        cart_id=cart_id,
        product_id=product_id,
        quantity=quantity,
        price_snapshot=price_snapshot,
    )
    item.id = item_id
    item.date_created = test_settings.TEST_DATETIME
    item.date_updated = None
    return item


def _make_cart_orm(
    cart_id: UUID = test_settings.TEST_CART_ID,
    user_id: UUID = test_settings.TEST_USER_ID,
    items: list[CartItem] | None = None,
) -> Cart:
    """Build a real Cart model instance for use in unit tests."""
    cart = Cart(user_id=user_id)
    cart.id = cart_id
    cart.date_created = test_settings.TEST_DATETIME
    cart.date_updated = None
    cart.items = items if items is not None else []
    return cart


@pytest.fixture
def mock_cart_item_orm() -> CartItem:
    """Fake SQLAlchemy CartItem ORM object."""
    return _make_cart_item_orm()


@pytest.fixture
def mock_cart_orm(mock_cart_item_orm: CartItem) -> Cart:
    """Fake SQLAlchemy Cart ORM object with one item."""
    return _make_cart_orm(items=[mock_cart_item_orm])


@pytest.fixture
def empty_cart_orm() -> Cart:
    """Fake SQLAlchemy Cart ORM object with no items."""
    return _make_cart_orm()


# ---------------------------------------------------------------------------
# Repository mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cart_repository() -> MagicMock:
    """Mock CartRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_cart_by_user_id = AsyncMock()
    repo.create = AsyncMock()
    repo.add_item_to_cart = AsyncMock()
    repo.update_item_quantity = AsyncMock()
    repo.remove_item = AsyncMock()
    repo.clear_cart = AsyncMock()
    repo.session = MagicMock()
    repo.session.refresh = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Service fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def cart_service_unit(mock_cart_repository: MagicMock) -> CartService:
    """CartService wired with a mocked repository."""
    return CartService(repository=mock_cart_repository)


# ---------------------------------------------------------------------------
# Route-level fixtures (unit tests)
# ---------------------------------------------------------------------------

def _make_cart_schema(
    cart_id: UUID = test_settings.TEST_CART_ID,
    user_id: UUID = test_settings.TEST_USER_ID,
    items: list[CartItemSchema] | None = None,
) -> CartSchema:
    """Helper to build a CartSchema for route mocks."""
    return CartSchema(
        id=cart_id,
        user_id=user_id,
        items=items if items is not None else [],
        date_created=test_settings.TEST_DATETIME,
        date_updated=None,
    )


@pytest.fixture
def mock_route_cart_service() -> MagicMock:
    """Full mock of CartService for app.dependency_overrides in route tests."""
    cart_schema = _make_cart_schema()
    summary_schema = CartSummary(
        id=test_settings.TEST_CART_ID,
        user_id=test_settings.TEST_USER_ID,
        items=[],
    )

    svc = MagicMock()
    svc.get_or_create_cart = AsyncMock(return_value=cart_schema)
    svc.get_cart_summary = AsyncMock(return_value=summary_schema)
    svc.add_item_to_cart = AsyncMock(return_value=cart_schema)
    svc.update_item_quantity = AsyncMock(return_value=cart_schema)
    svc.remove_item_from_cart = AsyncMock(return_value=cart_schema)
    svc.clear_cart = AsyncMock(return_value=None)
    return svc


# ---------------------------------------------------------------------------
# Route-level test client fixtures
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan to avoid DB/Redis/RabbitMQ connections during tests."""
    yield


@pytest.fixture
async def client_for_unit_testing(
    mock_route_cart_service: MagicMock,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP test client for route-level unit tests.

    - Replaces the FastAPI lifespan with a no-op so startup/shutdown don't
      attempt live connections.
    - Overrides the CartService dependency so no real DB is needed.
    """
    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_cart_service] = lambda: mock_route_cart_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
    settings.DEBUG_MODE = original_debug_mode


# ---------------------------------------------------------------------------
# Integration-test fixtures (real DB + real services)
# ---------------------------------------------------------------------------

@pytest.fixture
async def integration_client() -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP client for integration tests.

    What is real:
      - PostgreSQL (cart_service TEST database)
      - CartService, CartRepository

    What is mocked:
      - FastAPI lifespan (tables created directly via init_db)

    Isolation strategy:
      - Before yield : create all tables (idempotent) so the schema is fresh.
      - After  yield : TRUNCATE every table so the next test starts clean.
    """
    await test_cart_service_database_session_manager.init_db()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_cart_service_database_session_manager.transaction() as session:
            yield session

    def _override_get_cart_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> CartService:
        return CartService(CartRepository(session=session))

    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_cart_service] = _override_get_cart_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
    settings.DEBUG_MODE = original_debug_mode

    await test_cart_service_database_session_manager.truncate_all_tables()

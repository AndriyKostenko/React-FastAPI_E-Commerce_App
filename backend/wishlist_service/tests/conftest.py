"""
Shared pytest fixtures for wishlist_service unit and integration tests.

Unit-test fixtures replace all external dependencies (DB, Redis, RabbitMQ)
with mocks so the tests run without any live services.

Integration-test fixtures use the real PostgreSQL test database
(WISHLIST_SERVICE_TEST_DB) and truncate all tables between tests.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import Depends, Request
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from database_layer.wishlist_repository import WishlistRepository
from dependencies.dependencies import get_db_session, get_wishlist_service, get_current_user
from models.wishlist_models import Wishlist, WishlistItem
from service_layer.wishlist_service import WishlistService
from shared.schemas.wishlist_schemas import WishlistSchema, WishlistItemSchema
from shared.shared_instances import settings, test_wishlist_service_database_session_manager, test_settings
from shared.testing.helpers import allow_testserver_host


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

def _make_wishlist_item_orm(
    item_id: UUID = test_settings.TEST_WISHLIST_ITEM_ID,
    wishlist_id: UUID = test_settings.TEST_WISHLIST_ID,
    product_id: UUID = test_settings.TEST_PRODUCT_ID,
) -> WishlistItem:
    """Build a real WishlistItem model instance for use in unit tests."""
    item = WishlistItem(
        wishlist_id=wishlist_id,
        product_id=product_id,
    )
    item.id = item_id
    item.date_created = test_settings.TEST_DATETIME
    item.date_updated = None
    return item


def _make_wishlist_orm(
    wishlist_id: UUID = test_settings.TEST_WISHLIST_ID,
    user_id: UUID = test_settings.TEST_USER_ID,
    items: list[WishlistItem] | None = None,
) -> Wishlist:
    """Build a real Wishlist model instance for use in unit tests."""
    wishlist = Wishlist(user_id=user_id)
    wishlist.id = wishlist_id
    wishlist.date_created = test_settings.TEST_DATETIME
    wishlist.date_updated = None
    wishlist.items = items if items is not None else []
    return wishlist


@pytest.fixture
def mock_wishlist_item_orm() -> WishlistItem:
    """Fake SQLAlchemy WishlistItem ORM object."""
    return _make_wishlist_item_orm()


@pytest.fixture
def mock_wishlist_orm(mock_wishlist_item_orm: WishlistItem) -> Wishlist:
    """Fake SQLAlchemy Wishlist ORM object with one item."""
    return _make_wishlist_orm(items=[mock_wishlist_item_orm])


@pytest.fixture
def empty_wishlist_orm() -> Wishlist:
    """Fake SQLAlchemy Wishlist ORM object with no items."""
    return _make_wishlist_orm()


# ---------------------------------------------------------------------------
# Repository mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_wishlist_repository() -> MagicMock:
    """Mock WishlistRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_wishlist_by_user_id = AsyncMock()
    repo.create = AsyncMock()
    repo.add_item = AsyncMock()
    repo.remove_item = AsyncMock()
    repo.delete_wishlist_by_user_id = AsyncMock()
    repo.session = MagicMock()
    repo.session.refresh = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Service fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def wishlist_service_unit(mock_wishlist_repository: MagicMock) -> WishlistService:
    """WishlistService wired with a mocked repository."""
    return WishlistService(repository=mock_wishlist_repository)


# ---------------------------------------------------------------------------
# Route-level fixtures (unit tests)
# ---------------------------------------------------------------------------

def _make_wishlist_schema(
    wishlist_id: UUID = test_settings.TEST_WISHLIST_ID,
    user_id: UUID = test_settings.TEST_USER_ID,
    items: list[WishlistItemSchema] | None = None,
) -> WishlistSchema:
    """Helper to build a WishlistSchema for route mocks."""
    return WishlistSchema(
        id=wishlist_id,
        user_id=user_id,
        items=items if items is not None else [],
        date_created=test_settings.TEST_DATETIME,
        date_updated=None,
    )


@pytest.fixture
def mock_route_wishlist_service() -> MagicMock:
    """Full mock of WishlistService for app.dependency_overrides in route tests."""
    wishlist_schema = _make_wishlist_schema()

    svc = MagicMock()
    svc.get_or_create_wishlist = AsyncMock(return_value=wishlist_schema)
    svc.add_item_to_wishlist = AsyncMock(return_value=wishlist_schema)
    svc.remove_item_from_wishlist = AsyncMock(return_value=wishlist_schema)
    svc.delete_wishlist_by_user_id = AsyncMock(return_value=True)
    return svc


# ---------------------------------------------------------------------------
# Route-level test client fixtures
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan to avoid DB/Redis/RabbitMQ connections during tests."""
    yield


def _make_current_user_override(user_id: UUID):
    """Factory for a dependency override that injects request.state.current_user."""
    def _override() -> dict:
        return {"id": str(user_id), "role": test_settings.TEST_USER_ROLE}
    return _override


@pytest.fixture
async def client_for_unit_testing(
    mock_route_wishlist_service: MagicMock,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP test client for route-level unit tests.

    - Replaces the FastAPI lifespan with a no-op so startup/shutdown don't
      attempt live connections.
    - Overrides the WishlistService dependency so no real DB is needed.
    - Injects request.state.current_user so the /wishlists/me endpoints work.
    """
    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_wishlist_service] = lambda: mock_route_wishlist_service
    app.dependency_overrides[get_current_user] = _make_current_user_override(test_settings.TEST_USER_ID)
    app.state.http_session = MagicMock()

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
      - PostgreSQL (wishlist_service TEST database)
      - WishlistService, WishlistRepository

    What is mocked:
      - FastAPI lifespan (tables created directly via init_db)
      - Product Service HTTP validation (skipped when http_session is None)

    Isolation strategy:
      - Before yield : create all tables (idempotent) so the schema is fresh.
      - After  yield : TRUNCATE every table so the next test starts clean.
    """
    await test_wishlist_service_database_session_manager.init_db()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_wishlist_service_database_session_manager.transaction() as session:
            yield session

    def _override_get_wishlist_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> WishlistService:
        return WishlistService(WishlistRepository(session=session))

    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_wishlist_service] = _override_get_wishlist_service
    app.dependency_overrides[get_current_user] = _make_current_user_override(test_settings.TEST_USER_ID)
    app.state.http_session = None  # Skip product-service validation in integration tests

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
    settings.DEBUG_MODE = original_debug_mode

    await test_wishlist_service_database_session_manager.truncate_all_tables()

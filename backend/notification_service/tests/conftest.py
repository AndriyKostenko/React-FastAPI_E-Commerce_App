"""
Shared pytest fixtures for notification_service unit and integration tests.

Unit-test fixtures replace all external dependencies (DB, Redis, RabbitMQ)
with mocks so tests run without any live services.

Integration-test fixtures use the real PostgreSQL test database
(NOTIFICATION_SERVICE_TEST_DB) and truncate all tables between tests.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from database_layer.notification_repository import NotificationRepository
from dependencies.dependencies import get_db_session, get_notification_service
from service_layer.notification_service import NotificationService
from shared.shared_instances import settings, test_notification_service_database_session_manager, test_settings
from shared.schemas.notifications_schemas import NotificationInfo
from tests.constants import (
    TEST_NOTIFICATION_ID,
    TEST_USER_ID,
    TEST_MESSAGE,
    TEST_NOTIFICATION_TYPE,
    TEST_DATETIME,
    MOCK_NOTIFICATION_RESULT,
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
# ORM mock fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_notification_orm() -> MagicMock:
    """Fake SQLAlchemy Notification ORM object with all required attributes."""
    n = MagicMock()
    n.id = TEST_NOTIFICATION_ID
    n.user_id = TEST_USER_ID
    n.message = TEST_MESSAGE
    n.notification_type = TEST_NOTIFICATION_TYPE
    n.is_read = False
    n.date_created = TEST_DATETIME
    n.date_updated = None
    return n


# ---------------------------------------------------------------------------
# Repository mock fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_notification_repository() -> MagicMock:
    """Mock NotificationRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_by_user_id = AsyncMock()
    repo.get_unread_count = AsyncMock()
    repo.mark_all_as_read = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Service fixture (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def notification_service_unit(
    mock_notification_repository: MagicMock,
) -> NotificationService:
    """NotificationService wired with a mocked repository."""
    return NotificationService(repository=mock_notification_repository)


# ---------------------------------------------------------------------------
# Route-level fixtures (unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_route_notification_service() -> MagicMock:
    """Full mock of NotificationService for app.dependency_overrides in route tests."""
    _notif_info = test_settings.MOCK_NOTIFICATION_INFO
    svc = MagicMock()
    svc.get_user_notifications = AsyncMock(return_value=[_notif_info])
    svc.get_unread_count = AsyncMock(return_value=3)
    svc.get_notification_by_id = AsyncMock(return_value=_notif_info)
    svc.mark_as_read = AsyncMock(return_value=_notif_info)
    svc.mark_all_as_read = AsyncMock(return_value={"updated": 5})
    svc.delete_notification = AsyncMock(return_value=None)
    svc.save_notification = AsyncMock(return_value=_notif_info)
    return svc


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan to avoid DB/Redis/RabbitMQ connections during tests."""
    yield


@pytest.fixture
async def client_for_unit_testing(
    mock_route_notification_service: MagicMock,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP test client for route-level unit tests.
    Replaces the FastAPI lifespan with a no-op and overrides the notification service.
    """
    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_notification_service] = lambda: mock_route_notification_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_client:
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
      - PostgreSQL (notification_service TEST database)
      - NotificationService and NotificationRepository

    What is mocked:
      - FastAPI lifespan (tables created via init_db directly)

    Isolation:
      - Before yield: init schema (idempotent)
      - After  yield: TRUNCATE all tables
    """
    await test_notification_service_database_session_manager.init_db()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_notification_service_database_session_manager.transaction() as session:
            yield session

    def _override_get_notification_service(
        session: AsyncSession = Depends(_override_get_db_session),
    ) -> NotificationService:
        return NotificationService(repository=NotificationRepository(session=session))

    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_notification_service] = _override_get_notification_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
    settings.DEBUG_MODE = original_debug_mode

    await test_notification_service_database_session_manager.truncate_all_tables()

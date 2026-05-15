"""
Shared pytest fixtures for user_service unit and route tests.

All fixtures use function scope (default) to ensure full isolation
between tests.  Heavy external dependencies (DB, Redis, RabbitMQ)
are replaced with mocks so the tests run without any live services.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from typing import Any

import pytest
from fastapi import Depends
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from database_layer.user_repository import UserRepository
from dependencies.dependencies import get_user_service, get_current_user, get_db_session
from service_layer.user_service import UserService
from shared.shared_instances import test_settings, settings, test_user_service_database_session_manager
from shared.managers.token_manager import TokenManager
from shared.managers.password_manager import PasswordManager


# ---------------------------------------------------------------------------
# ORM / DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_user_orm() -> MagicMock:
    """Fake SQLAlchemy User ORM object with all UserInfo-required attributes."""
    user = MagicMock()
    user.id = test_settings.TEST_USER_ID
    user.name = test_settings.TEST_NAME
    user.email = test_settings.TEST_EMAIL
    user.hashed_password = test_settings.TEST_HASHED_PW
    user.role = test_settings.TEST_USER_ROLE
    user.phone_number = None
    user.image = None
    user.is_active = True
    user.is_verified = True
    user.date_created = test_settings.TEST_DATETIME
    user.date_updated = test_settings.TEST_DATETIME
    return user

@pytest.fixture
def mock_repository() -> MagicMock:
    """Mock UserRepository — all async methods are AsyncMock instances."""
    repo = MagicMock()
    repo.get_by_field = AsyncMock()
    repo.create = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update_by_field = AsyncMock()
    repo.update_by_id = AsyncMock()
    repo.delete_by_id = AsyncMock()
    repo.get_verified_users = AsyncMock()
    repo.get_users_by_role = AsyncMock()
    return repo

# ---------------------------------------------------------------------------
# Managers fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_password_manager() -> MagicMock:
    """Mock PasswordManager with sensible default return values."""
    mgr = MagicMock()
    mgr.hash_password = MagicMock(return_value="$2b$12$mocked_hashed_password")
    mgr.verify_password = MagicMock(return_value=True)
    return mgr

@pytest.fixture
def mock_token_manager() -> MagicMock:
    """Mock TokenManager — sync methods return (token_str, expiry_int)."""
    mgr = MagicMock()
    mgr.create_access_token = MagicMock(return_value=("mock_access_token", 9_999_999_999))
    mgr.create_refresh_token = MagicMock(return_value=("mock_refresh_token", 9_999_999_999))
    mgr.decode_token = MagicMock()
    return mgr

@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock aioredis client returned by RedisManager.redis property."""
    redis = AsyncMock()
    redis.setex = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=1)
    return redis

@pytest.fixture
def mock_redis_manager(mock_redis: AsyncMock) -> MagicMock:
    """Mock RedisManager whose .redis property returns mock_redis."""
    mgr = MagicMock()
    type(mgr).redis = PropertyMock(return_value=mock_redis)
    return mgr

@pytest.fixture
def token_manager() -> TokenManager:
    return TokenManager(settings=test_settings)

@pytest.fixture
def password_manager() -> PasswordManager:
    return PasswordManager(settings=test_settings)

# ---------------------------------------------------------------------------
# Service fixture (unit tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def user_service(
    mock_repository: MagicMock,
    mock_password_manager: MagicMock,
    mock_token_manager: MagicMock,
    mock_redis_manager: MagicMock) -> UserService:
    """UserService instance wired with all mocked dependencies."""
    return UserService(
        repository=mock_repository,
        password_manager=mock_password_manager,
        token_manager=mock_token_manager,
        redis_manager=mock_redis_manager)

#---------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
@pytest.fixture
def admin_user() -> dict[str, str|int]:
    return {'email': 'a.kostenkouk@gmail.com', 'id': 1, 'user_role': settings.SECRET_ROLE}

@pytest.fixture
def normal_user() -> dict[str, str|int]:
    return {'email': 'a.kostenkouk@gmail.com', 'id': 1, 'user_role': 'user'}

# ---------------------------------------------------------------------------
# Route-level fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_route_service() -> MagicMock:
    """Full mock of UserService for use via app.dependency_overrides in route tests."""
    svc = MagicMock()
    svc.create_user = AsyncMock(return_value=(test_settings.USER_INFO, "verification_token_abc"))
    svc.verify_email = AsyncMock(return_value=test_settings.USER_INFO)
    svc.request_password_reset = AsyncMock(return_value=(test_settings.USER_INFO, "reset_token_abc"))
    svc.reset_password_with_token = AsyncMock(return_value=test_settings.USER_INFO)
    svc.login_user = AsyncMock(
        return_value=(
            test_settings.CURRENT_USER,
            "access_tok",
            9_999_999_999,
            "refresh_tok",
            9_999_999_999,
        )
    )
    svc.refresh_access_token = AsyncMock(return_value=("new_access_tok", 9_999_999_999))
    svc.logout_user = AsyncMock(return_value=None)
    svc.get_user_by_id = AsyncMock(return_value=test_settings.USER_INFO)
    svc.get_all_users = AsyncMock(return_value=[test_settings.USER_INFO])
    svc.update_user_basic_info = AsyncMock(return_value=test_settings.USER_INFO)
    svc.delete_user_by_id = AsyncMock(return_value=None)
    svc.get_current_user_from_token = AsyncMock(return_value=test_settings.CURRENT_USER)
    return svc


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan replaces the real one in route tests to avoid DB/Redis/RabbitMQ connections."""
    yield


@pytest.fixture
async def client_for_unit_testing(mock_route_service: MagicMock) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP test client for route tests.

    - Replaces the FastAPI lifespan with a no-op so startup/shutdown don't
      attempt live connections to PostgreSQL, Redis, or RabbitMQ.
    - Overrides the get_user_service and get_current_user FastAPI dependencies.
    - Patches user_events_publisher so events are not published to RabbitMQ.
    """

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    with patch("routes.user_routes.user_events_publisher") as mock_pub:
        mock_pub.publish_user_registered = AsyncMock()
        mock_pub.publish_email_verified = AsyncMock()
        mock_pub.publish_password_reset_request = AsyncMock()
        mock_pub.publish_password_reset_success = AsyncMock()
        mock_pub.publish_user_logged_in = AsyncMock()

        app.dependency_overrides[get_user_service] = lambda: mock_route_service
        app.dependency_overrides[get_current_user] = lambda: test_settings.CURRENT_USER

        async with AsyncClient(transport=ASGITransport(app=app),base_url="http://testserver") as async_client:
            yield async_client

        app.dependency_overrides.clear()

    app.router.lifespan_context = original_lifespan

# ---------------------------------------------------------------------------
# Integration-test fixtures  (real DB + real service + mock Redis/events)
# ---------------------------------------------------------------------------

@pytest.fixture
async def mock_user_events_publisher():
    """Patches the RabbitMQ event publisher used by user routes.

    Yielded mock allows tests to inspect published events, e.g. to extract
    the verification token from publish_user_registered.call_args.
    """
    with patch("routes.user_routes.user_events_publisher") as mock_pub:
        mock_pub.publish_user_registered        = AsyncMock()
        mock_pub.publish_email_verified         = AsyncMock()
        mock_pub.publish_password_reset_request = AsyncMock()
        mock_pub.publish_password_reset_success = AsyncMock()
        mock_pub.publish_user_logged_in         = AsyncMock()
        yield mock_pub


@pytest.fixture
async def integration_client(mock_user_events_publisher) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP client for integration tests.

    What is real:
      - PostgreSQL (user_service TEST database)
      - UserService, UserRepository
      - PasswordManager, TokenManager

    What is mocked:
      - Redis  (no live Redis needed in CI)
      - RabbitMQ event publisher (via mock_user_events_publisher fixture)
      - FastAPI lifespan (tables are managed by this fixture directly)

    Isolation strategy:
      - Before yield : create all tables (idempotent) so the schema is fresh.
      - After  yield : TRUNCATE every table so the next test starts clean.
    """
    # ── 1. Ensure the test schema exists ────────────────────────────────────
    await test_user_service_database_session_manager.init_db()

    # ── 2. Build real managers ───────────────────────────────────────────────
    real_password_manager = PasswordManager(settings)
    real_token_manager    = TokenManager(settings)

    # ── 3. Mock Redis (no live Redis needed) ────────────────────────────────
    _mock_redis = AsyncMock()
    _mock_redis.setex  = AsyncMock(return_value=True)
    _mock_redis.get    = AsyncMock(return_value=None)   # no cached tokens → always "valid"
    _mock_redis.delete = AsyncMock(return_value=1)

    _mock_redis_manager = MagicMock()
    type(_mock_redis_manager).redis = PropertyMock(return_value=_mock_redis)

    # ── 4. Dependency overrides ──────────────────────────────────────────────
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_user_service_database_session_manager.transaction() as session:
            yield session

    async def _override_get_user_service(session: AsyncSession = Depends(_override_get_db_session)) -> UserService:
        return UserService(
            repository=UserRepository(session=session),
            password_manager=real_password_manager,
            token_manager=real_token_manager,
            redis_manager=_mock_redis_manager,
        )

    # ── 5. Replace the app lifespan so no live infra connections are made ───
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    app.dependency_overrides[get_db_session]   = _override_get_db_session
    app.dependency_overrides[get_user_service] = _override_get_user_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan

    # ── 6. Wipe all rows so the next test starts with an empty database ─────
    await test_user_service_database_session_manager.truncate_all_tables()

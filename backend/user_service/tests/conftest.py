"""
Shared pytest fixtures for user_service unit and route tests.

All fixtures use function scope (default) to ensure full isolation
between tests.  Heavy external dependencies (DB, Redis, RabbitMQ)
are replaced with mocks so the tests run without any live services.
"""
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from typing import Any

import pytest
from fastapi import Depends
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from main import app
from database_layer.user_repository import UserRepository
from dependencies.dependencies import (
    admin_only_dependency,
    get_current_user,
    get_db_session,
    get_user_service,
    self_or_admin,
)
from service_layer.user_service import UserService
from service_layer.outbox_event_service import OutboxEventService
from shared.database_layer.outbox_repository import OutboxRepository
from models.base import Base
from models.outbox_models import OutboxEvent
from models.user_models import User
from managers import ResourceManager, UserApiResources, logger, settings
from shared.settings import get_test_settings
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.managers.token_manager import TokenManager
from shared.testing.signing_keys import EphemeralSigningKeys

# One set of throwaway keys for the whole session, playing both user-service's
# token key and the gateway's assertion key — so an integration test can log
# in, then call a protected route exactly the way the gateway would.
SIGNING_KEYS = EphemeralSigningKeys()
from shared.managers.password_manager import PasswordManager
from schemas.user_schemas import CurrentUserInfo, UserInfo


from shared.testing.helpers import allow_testserver_host


test_settings = get_test_settings()

TEST_USER_INFO = UserInfo(
    id=test_settings.TEST_USER_ID,
    name=test_settings.TEST_NAME,
    email=test_settings.TEST_EMAIL,
    role=test_settings.TEST_USER_ROLE,
    phone_number=test_settings.TEST_PHONE_NUMBER,
    image=None,
    date_created=test_settings.TEST_DATETIME,
    date_updated=test_settings.TEST_DATETIME,
    is_verified=True,
    is_active=True,
)
TEST_CURRENT_USER = CurrentUserInfo(
    email=test_settings.TEST_EMAIL,
    id=test_settings.TEST_USER_ID,
    role=test_settings.TEST_USER_ROLE,
)



def _admin_only_guard():
    """The callable behind ``admin_only_dependency``.

    It is produced by the ``require_roles`` factory, so the only stable handle
    on it is the Depends marker stored in the Annotated alias — building a new
    one with ``require_roles(...)`` would create a different object that
    ``dependency_overrides`` would never match.
    """
    return admin_only_dependency.__metadata__[0].dependency

# ---------------------------------------------------------------------------
# Host-validation bypass for ASGI test client
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _allow_testserver_host() -> None:
    """Make the default httpx/TestClient host ('testserver') pass host checks."""
    allow_testserver_host()


@pytest.fixture(scope="session")
async def test_database_session_manager(
) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    """Own and close the user test database manager for this session."""
    manager = TestDatabaseSessionManager(
        database_url=settings.USER_SERVICE_TEST_DATABASE_URL,
        logger=logger,
    )
    try:
        yield manager
    finally:
        await manager.close()


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
    user.token_version = 1
    user.deleted_at = None
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
    repo.commit = AsyncMock()
    return repo

# ---------------------------------------------------------------------------
# Managers fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_password_manager() -> MagicMock:
    """Mock PasswordManager with sensible default return values."""
    mgr = MagicMock()
    mgr.hash_password = MagicMock(return_value="$2b$12$mocked_hashed_password")
    mgr.dummy_hash = MagicMock(return_value="$2b$12$mocked_dummy_password_hash")
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
    redis.getdel = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=1)
    redis.sadd = AsyncMock(return_value=1)
    redis.srem = AsyncMock(return_value=1)
    redis.smembers = AsyncMock(return_value=set())

    # redis-py creates pipelines synchronously; only execute() is awaited.
    pipeline = MagicMock()
    pipeline.setex = MagicMock(return_value=pipeline)
    pipeline.sadd = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.delete = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[])
    redis.pipeline = MagicMock(return_value=pipeline)
    return redis

@pytest.fixture
def mock_redis_manager(mock_redis: AsyncMock) -> MagicMock:
    """Mock RedisManager whose .redis property returns mock_redis."""
    mgr = MagicMock()
    type(mgr).redis = PropertyMock(return_value=mock_redis)
    return mgr

@pytest.fixture
def mock_outbox_event_service() -> MagicMock:
    """Mock OutboxEventService — records events without touching the database."""
    svc = MagicMock()
    svc.add_outbox_event = AsyncMock(return_value=None)
    svc.get_all_events = AsyncMock(return_value=[])
    svc.get_unprocessed_events = AsyncMock(return_value=[])
    svc.mark_event_as_processed = AsyncMock(return_value=None)
    return svc

@pytest.fixture
def token_manager() -> TokenManager:
    return EphemeralSigningKeys().token_manager(test_settings)

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
    mock_redis_manager: MagicMock,
    mock_outbox_event_service: MagicMock) -> UserService:
    """UserService instance wired with all mocked dependencies."""
    return UserService(
        repository=mock_repository,
        password_manager=mock_password_manager,
        token_manager=mock_token_manager,
        cache_manager=mock_redis_manager,
        outbox_event_service=mock_outbox_event_service,
        http_client=AsyncMock(),
        settings=settings,
    )

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
    svc.create_user = AsyncMock(return_value=(TEST_USER_INFO, "verification_token_abc"))
    svc.verify_email = AsyncMock(return_value=TEST_USER_INFO)
    svc.request_password_reset = AsyncMock(return_value=(TEST_USER_INFO, "reset_token_abc"))
    svc.reset_password_with_token = AsyncMock(return_value=TEST_USER_INFO)
    svc.login_user = AsyncMock(
        return_value=(
            TEST_CURRENT_USER,
            "access_tok",
            9_999_999_999,
            "refresh_tok",
            9_999_999_999,
        )
    )
    svc.refresh_access_token = AsyncMock(
        return_value=("new_access_tok", 9_999_999_999, "rotated_refresh_tok", 9_999_999_999)
    )
    svc.logout_user = AsyncMock(return_value=None)
    svc.get_user_by_id = AsyncMock(return_value=TEST_USER_INFO)
    svc.get_all_users = AsyncMock(return_value=[TEST_USER_INFO])
    svc.update_user_basic_info = AsyncMock(return_value=TEST_USER_INFO)
    svc.delete_user_by_id = AsyncMock(return_value=None)
    svc.get_active_user = AsyncMock(return_value=TEST_CURRENT_USER)
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
    - Bypasses host validation middleware so tests can use the default testserver host.
    """

    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    test_resources = UserApiResources(
        settings=settings,
        logger=logger,
        database=MagicMock(),
        cache=MagicMock(),
        rate_limiter=MagicMock(is_rate_limited=AsyncMock(return_value=False)),
        google_http_client=AsyncMock(),
        password_manager=MagicMock(),
        token_manager=MagicMock(),
        session_registry=MagicMock(
            publish_generation=AsyncMock(return_value=None),
            is_revoked=AsyncMock(return_value=False),
        ),
    )
    ResourceManager.attach(app, test_resources)

    app.dependency_overrides[get_user_service] = lambda: mock_route_service
    app.dependency_overrides[get_current_user] = lambda: TEST_CURRENT_USER

    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()

    app.router.lifespan_context = original_lifespan
    ResourceManager.detach(app)
    settings.DEBUG_MODE = original_debug_mode

@pytest.fixture
async def get_outbox_event(
    test_database_session_manager: TestDatabaseSessionManager,
) -> AsyncGenerator[Callable[[str], Awaitable[dict[str, Any] | None]], Any]:
    """Return a helper that reads the latest unprocessed outbox event payload by event_type."""
    async def _query(event_type: str) -> dict[str, Any] | None:
        async with test_database_session_manager.transaction() as session:
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.event_type == event_type, OutboxEvent.processed.is_(False))
                .order_by(OutboxEvent.date_created.desc())
            )
            event = result.scalars().first()
            return event.payload if event else None

    yield _query


# ---------------------------------------------------------------------------
# Integration-test fixtures  (real DB + real service + mock Redis/events)
# ---------------------------------------------------------------------------

@pytest.fixture
async def integration_client(
    test_database_session_manager: TestDatabaseSessionManager,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Async HTTP client for integration tests.

    What is real:
      - PostgreSQL (user_service TEST database)
      - UserService, UserRepository, OutboxEventService, OutboxRepository
      - PasswordManager, TokenManager

    What is mocked:
      - Redis  (no live Redis needed in CI)
      - RabbitMQ event publisher (the outbox poller is not started because the lifespan is no-op)
      - FastAPI lifespan (tables are managed by this fixture directly)

    Isolation strategy:
      - Before yield : create all tables (idempotent) so the schema is fresh.
      - After  yield : TRUNCATE every table so the next test starts clean.
    """
    # ── 1. Ensure the test schema exists ────────────────────────────────────
    await test_database_session_manager.init_db(Base.metadata)

    # ── 2. Build real managers ───────────────────────────────────────────────
    real_password_manager = PasswordManager(settings)
    real_token_manager    = SIGNING_KEYS.token_manager(settings)

    # ── 3. Fake Redis — dict-backed, so token flows behave like production ───
    #
    # Refresh tokens are written through a pipeline and read back on refresh,
    # verification tokens are consumed with GETDEL, and deleting a user revokes
    # a whole token set. A fake that only records calls would let all of those
    # pass without ever storing anything, so this one keeps real state.
    _redis_store: dict[str, Any] = {}

    async def _redis_setex(key, ttl, value):
        _redis_store[key] = value
        return True

    async def _redis_get(key):
        return _redis_store.get(key)

    async def _redis_delete(*keys):
        for k in keys:
            _redis_store.pop(k, None)
        return len(keys)

    async def _redis_getdel(key):
        """Read and consume in one step, as single-use tokens require."""
        return _redis_store.pop(key, None)

    async def _redis_sadd(key, *members):
        bucket = _redis_store.setdefault(key, set())
        bucket.update(members)
        return len(members)

    async def _redis_srem(key, *members):
        bucket = _redis_store.get(key)
        if not isinstance(bucket, set):
            return 0
        removed = len(bucket & set(members))
        bucket -= set(members)
        return removed

    async def _redis_smembers(key):
        bucket = _redis_store.get(key)
        return set(bucket) if isinstance(bucket, set) else set()

    async def _redis_expire(key, ttl):
        return key in _redis_store

    class _FakePipeline:
        """Buffers commands and applies them on execute(), like redis-py.

        redis-py builds the pipeline synchronously and awaits only execute(),
        so the buffering methods here are deliberately not coroutines.
        """

        _COMMANDS = {
            "setex": _redis_setex,
            "sadd": _redis_sadd,
            "srem": _redis_srem,
            "delete": _redis_delete,
            "expire": _redis_expire,
        }

        def __init__(self) -> None:
            self._queued: list[tuple[str, tuple[Any, ...]]] = []

        def __getattr__(self, name: str):
            if name not in self._COMMANDS:
                raise AttributeError(name)

            def _queue(*args):
                self._queued.append((name, args))
                return self

            return _queue

        async def execute(self):
            results = []
            for name, args in self._queued:
                results.append(await self._COMMANDS[name](*args))
            self._queued.clear()
            return results

    _mock_redis = MagicMock()
    _mock_redis.setex    = _redis_setex
    _mock_redis.get      = _redis_get
    _mock_redis.delete   = _redis_delete
    _mock_redis.getdel   = _redis_getdel
    _mock_redis.sadd     = _redis_sadd
    _mock_redis.srem     = _redis_srem
    _mock_redis.smembers = _redis_smembers
    _mock_redis.expire   = _redis_expire
    _mock_redis.pipeline = MagicMock(side_effect=_FakePipeline)

    _mock_redis_manager = MagicMock()
    type(_mock_redis_manager).redis = PropertyMock(return_value=_mock_redis)

    # ── 4. Dependency overrides ──────────────────────────────────────────────
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_database_session_manager.transaction() as session:
            yield session

    async def _override_get_user_service(session: AsyncSession = Depends(_override_get_db_session)) -> UserService:
        return UserService(
            repository=UserRepository(session=session),
            password_manager=real_password_manager,
            token_manager=real_token_manager,
            cache_manager=_mock_redis_manager,
            outbox_event_service=OutboxEventService(repository=OutboxRepository(session=session, model=OutboxEvent)),
            http_client=AsyncMock(),
            settings=settings,
        )

    # ── 5. Replace the app lifespan so no live infra connections are made ───
    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    ResourceManager.attach(app, UserApiResources(
        settings=settings,
        logger=logger,
        database=test_database_session_manager,
        cache=_mock_redis_manager,
        rate_limiter=MagicMock(is_rate_limited=AsyncMock(return_value=False)),
        google_http_client=AsyncMock(),
        password_manager=real_password_manager,
        token_manager=real_token_manager,
        # Revocation is broadcast through this; a stub keeps the integration
        # tests off Redis while still exercising the call.
        session_registry=MagicMock(
            publish_generation=AsyncMock(return_value=None),
            is_revoked=AsyncMock(return_value=False),
        ),
    ))

    # The /users endpoints sit behind role checks. Override only the
    # authorisation layer, not get_current_user itself: the /me tests assert
    # what an absent or invalid token does, and replacing the authentication
    # dependency wholesale would quietly make those pass for the wrong reason.
    def _override_authorised_admin() -> CurrentUserInfo:
        return CurrentUserInfo(
            email=test_settings.TEST_EMAIL,
            id=test_settings.TEST_USER_ID,
            role=settings.SECRET_ROLE,
        )

    app.dependency_overrides[get_db_session]   = _override_get_db_session
    app.dependency_overrides[get_user_service] = _override_get_user_service
    for _guard in (self_or_admin, _admin_only_guard()):
        app.dependency_overrides[_guard] = _override_authorised_admin

    SIGNING_KEYS.install_verifier(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan
    ResourceManager.detach(app)
    settings.DEBUG_MODE = original_debug_mode

    # ── 6. Wipe all rows so the next test starts with an empty database ─────
    await test_database_session_manager.truncate_all_tables(Base.metadata)


def as_gateway(access_token: str, method: str, path: str) -> dict[str, str]:
    """
    What the gateway sends user-service for a request carrying ``access_token``:
    it verifies the token, then signs an assertion for this method and path.
    """
    claims = SIGNING_KEYS.user_token_verifier().decode(access_token)
    return SIGNING_KEYS.caller_headers(method, path, user_id=claims.id, role=claims.role or "user", email=str(claims.email))

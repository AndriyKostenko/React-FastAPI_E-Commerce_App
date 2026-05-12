"""
Shared pytest fixtures for user_service unit tests.

All fixtures use function scope (default) to ensure full isolation
between tests.  Heavy external dependencies (DB, Redis, RabbitMQ)
are replaced with mocks so the tests run without any live services.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import UUID, uuid4

import pytest

from service_layer.user_service import UserService


# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

TEST_USER_ID: UUID = uuid4()
TEST_EMAIL: str = "test@example.com"
TEST_NAME: str = "Test User"
TEST_HASHED_PW: str = "$2b$12$fakehashfortesting000000000000000000"
TEST_DATETIME: datetime = datetime(2024, 1, 1, 12, 0, 0)


# ---------------------------------------------------------------------------
# ORM / DB fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user_orm() -> MagicMock:
    """Fake SQLAlchemy User ORM object with all UserInfo-required attributes."""
    user = MagicMock()
    user.id = TEST_USER_ID
    user.name = TEST_NAME
    user.email = TEST_EMAIL
    user.hashed_password = TEST_HASHED_PW
    user.role = "user"
    user.phone_number = None
    user.image = None
    user.is_active = True
    user.is_verified = True
    user.date_created = TEST_DATETIME
    user.date_updated = None
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
# Manager fixtures
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


# ---------------------------------------------------------------------------
# Service fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def user_service(
    mock_repository: MagicMock,
    mock_password_manager: MagicMock,
    mock_token_manager: MagicMock,
    mock_redis_manager: MagicMock,
) -> UserService:
    """UserService instance wired with all mocked dependencies."""
    return UserService(
        repository=mock_repository,
        password_manager=mock_password_manager,
        token_manager=mock_token_manager,
        redis_manager=mock_redis_manager,
    )

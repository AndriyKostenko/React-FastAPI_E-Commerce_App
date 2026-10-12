"""The pool each process opens is the one its settings name, not a CPU guess."""

from logging import getLogger

import pytest

from infrastructure.database_layer.pool_settings import PoolSettings
from infrastructure.managers.database_session_manager import DatabaseSessionManager
from settings import Settings

# Built but never connected: creating an engine opens no connection.
UNUSED_URL = "postgresql+asyncpg://user:password@127.0.0.1:1/unused"


def test_an_api_process_defaults_to_three_plus_two() -> None:
    fields = Settings.model_fields
    assert (fields["DB_POOL_SIZE"].default, fields["DB_MAX_OVERFLOW"].default) == (3, 2)


@pytest.mark.parametrize(("pool_size", "max_overflow"), [(3, 2), (1, 1), (1, 0)])
def test_the_engine_gets_exactly_the_configured_pool(pool_size: int, max_overflow: int) -> None:
    manager = DatabaseSessionManager(
        UNUSED_URL, getLogger("test"), pool_size=pool_size, max_overflow=max_overflow, pool_timeout=7
    )
    assert manager.async_engine is not None
    pool = manager.async_engine.sync_engine.pool
    assert pool.size() == pool_size
    assert pool._max_overflow == max_overflow  # noqa: SLF001 - no public accessor
    assert pool._timeout == 7  # noqa: SLF001


@pytest.mark.parametrize(("pool_size", "max_overflow"), [(0, 1), (1, -1)])
def test_a_pool_that_could_never_serve_is_refused(pool_size: int, max_overflow: int) -> None:
    with pytest.raises(ValueError):
        PoolSettings(pool_size=pool_size, max_overflow=max_overflow)

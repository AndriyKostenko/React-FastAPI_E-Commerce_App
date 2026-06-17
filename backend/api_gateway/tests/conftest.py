"""
Shared pytest fixtures for api_gateway unit tests.

Strategy:
  - No database — api_gateway is a pure proxy service.
  - The lifespan (Redis + httpx client init) is replaced with a no-op.
  - auth_middleware.middleware is patched to inject a mock user (bypass JWT validation).
  - All CacheManager and RateLimitManager async methods (rate-limiter, cache) are patched to no-ops.
  - api_gateway_manager.forward_request is patched per-test via the `mock_forward` fixture.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse
from httpx import AsyncClient, ASGITransport

from main import app
from middleware.auth_middleware import auth_middleware
from gateway.apigateway import api_gateway_manager
from shared.shared_instances import api_gateway_cache_manager, api_gateway_rate_limit_manager, settings, test_settings
from shared.schemas.user_schemas import CurrentUserInfo
from tests.constants import (
    TEST_USER_ID,
    TEST_ADMIN_ID,
    TEST_USER_EMAIL,
    TEST_ADMIN_EMAIL,
    TEST_USER_ROLE,
    TEST_ADMIN_ROLE,
    MOCK_UPSTREAM_RESPONSE_BODY,
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
# Mock users — sourced directly from shared TestSettings
# ---------------------------------------------------------------------------

TEST_REGULAR_USER = test_settings.CURRENT_USER
TEST_ADMIN_USER   = test_settings.ADMIN_USER


# ---------------------------------------------------------------------------
# No-op lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _noop_lifespan(app):
    """Skip Redis + httpx client init during tests."""
    yield


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_forward() -> AsyncMock:
    """Default mock for api_gateway_manager.forward_request → returns 200."""
    return AsyncMock(
        return_value=JSONResponse(
            content=MOCK_UPSTREAM_RESPONSE_BODY,
            status_code=200,
        )
    )


def _make_client(current_user: CurrentUserInfo, mock_forward: AsyncMock):
    """Context manager returning an AsyncClient with all gateway dependencies mocked."""

    original_debug_mode = settings.DEBUG_MODE
    settings.DEBUG_MODE = True

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    async def _bypass_auth(request, call_next):
        """Auth middleware replacement: injects current_user and passes through."""
        request.state.current_user = current_user
        return await call_next(request)

    patches = [
        patch.object(auth_middleware, "middleware", side_effect=_bypass_auth),
        patch.object(api_gateway_rate_limit_manager, "is_rate_limited", new=AsyncMock(return_value=False)),
        patch.object(api_gateway_cache_manager, "get_cached_response", new=AsyncMock(return_value=None)),
        patch.object(api_gateway_cache_manager, "cache_response", new=AsyncMock()),
        patch.object(api_gateway_cache_manager, "invalidate_namespace", new=AsyncMock()),
        patch.object(api_gateway_manager, "forward_request", mock_forward),
    ]

    class _ClientContextManager:
        async def __aenter__(self):
            for p in patches:
                p.start()
            self._client = AsyncClient(
                transport=ASGITransport(app=app), base_url="http://testserver"
            )
            return await self._client.__aenter__()

        async def __aexit__(self, *args):
            await self._client.__aexit__(*args)
            for p in reversed(patches):
                p.stop()
            app.router.lifespan_context = original_lifespan
            settings.DEBUG_MODE = original_debug_mode

    return _ClientContextManager()


@pytest.fixture
async def client(mock_forward: AsyncMock) -> AsyncGenerator[AsyncClient, Any]:
    """AsyncClient logged in as a regular user."""
    async with _make_client(TEST_REGULAR_USER, mock_forward) as c:
        yield c


@pytest.fixture
async def admin_client(mock_forward: AsyncMock) -> AsyncGenerator[AsyncClient, Any]:
    """AsyncClient logged in as an admin user."""
    async with _make_client(TEST_ADMIN_USER, mock_forward) as c:
        yield c

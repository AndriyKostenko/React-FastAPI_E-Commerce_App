"""Unit tests for AuthMiddleware.is_public_endpoint and middleware logic."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders

from middleware.auth_middleware import AuthMiddleware
from shared.shared_instances import settings


def _make_request(path: str, method: str, headers: dict | None = None, cookies: dict | None = None) -> MagicMock:
    req = MagicMock(spec=Request)
    req.url.path = path
    req.method = method
    req.headers = MutableHeaders(headers=headers or {})
    req.cookies = cookies or {}
    req.state = MagicMock()
    return req


API = settings.API_GATEWAY_SERVICE_URL_API_VERSION  # "/api/v1"


class TestIsPublicEndpoint:
    """Tests for the pure-logic public-endpoint check."""

    @pytest.fixture
    def middleware(self) -> AuthMiddleware:
        return AuthMiddleware.__new__(AuthMiddleware)

    def setup_method(self):
        """Re-create a fresh middleware instance (bypassing singleton for tests)."""
        self.mw = AuthMiddleware.__new__(AuthMiddleware)
        self.mw.__init__(settings=settings, logger=MagicMock())

    def test_health_endpoint_is_public(self):
        assert self.mw.is_public_endpoint("/health", "GET") is True

    def test_docs_endpoint_is_public(self):
        assert self.mw.is_public_endpoint("/docs", "GET") is True

    def test_media_prefix_is_public(self):
        assert self.mw.is_public_endpoint("/media/generated/test.png", "GET") is True

    def test_register_post_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/register", "POST") is True

    def test_register_get_is_not_public(self):
        assert self.mw.is_public_endpoint(f"{API}/register", "GET") is False

    def test_login_post_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/login", "POST") is True

    def test_refresh_post_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/refresh", "POST") is True

    def test_logout_post_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/logout", "POST") is True

    def test_forgot_password_post_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/forgot-password", "POST") is True

    def test_products_get_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/products", "GET") is True

    def test_products_post_is_not_public(self):
        assert self.mw.is_public_endpoint(f"{API}/products", "POST") is False

    def test_categories_get_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/categories", "GET") is True

    def test_customization_pricing_get_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/customization/pricing", "GET") is True

    def test_images_generations_post_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/images/generations", "POST") is True

    def test_images_generations_status_get_is_public(self):
        from uuid import uuid4
        job_id = str(uuid4())
        assert self.mw.is_public_endpoint(f"{API}/images/generations/{job_id}/status", "GET") is True

    def test_images_generations_status_post_is_not_public(self):
        from uuid import uuid4
        job_id = str(uuid4())
        assert self.mw.is_public_endpoint(f"{API}/images/generations/{job_id}/status", "POST") is False

    def test_images_generations_get_is_not_public(self):
        """GET on the base generations path (without job id) should NOT be public."""
        assert self.mw.is_public_endpoint(f"{API}/images/generations", "GET") is False

    def test_payments_webhook_post_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/payments/webhook", "POST") is True

    def test_users_user_id_get_is_not_public(self):
        assert self.mw.is_public_endpoint(f"{API}/users/abc-123", "GET") is False

    def test_notifications_get_is_not_public(self):
        assert self.mw.is_public_endpoint(f"{API}/notifications", "GET") is False

    def test_admin_schema_users_get_is_public(self):
        assert self.mw.is_public_endpoint(f"{API}/admin/schema/users", "GET") is True


class TestMiddlewareAuth:
    """Tests for the middleware function: token extraction, validation, pass-through."""

    def setup_method(self):
        self.mw = AuthMiddleware.__new__(AuthMiddleware)
        self.mw.__init__(settings=settings, logger=MagicMock())

    async def test_options_request_passes_through(self):
        req = _make_request("/api/v1/users", "OPTIONS")
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        response = await self.mw.middleware(req, call_next)

        call_next.assert_awaited_once_with(req)
        assert response.status_code == 200

    async def test_public_endpoint_passes_through_without_token(self):
        req = _make_request(f"{API}/products", "GET")
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        response = await self.mw.middleware(req, call_next)

        call_next.assert_awaited_once()
        assert response.status_code == 200

    async def test_protected_endpoint_without_token_returns_401(self):
        req = _make_request(f"{API}/users/abc", "GET")
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        response = await self.mw.middleware(req, call_next)

        assert response.status_code == 401
        call_next.assert_not_awaited()

    async def test_protected_endpoint_with_valid_bearer_token_passes(self):
        req = _make_request(
            f"{API}/users/abc", "GET",
            headers={"Authorization": "Bearer valid.jwt.token"},
        )
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        mock_user = MagicMock()
        mock_user.email = "user@example.com"

        with patch("middleware.auth_middleware.token_manager.decode_token", return_value=mock_user):
            response = await self.mw.middleware(req, call_next)

        call_next.assert_awaited_once()
        assert response.status_code == 200

    async def test_protected_endpoint_with_invalid_token_returns_401(self):
        from fastapi import HTTPException
        req = _make_request(
            f"{API}/users/abc", "GET",
            headers={"Authorization": "Bearer bad.token"},
        )
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        with patch(
            "middleware.auth_middleware.token_manager.decode_token",
            side_effect=HTTPException(status_code=401, detail="Token expired"),
        ):
            response = await self.mw.middleware(req, call_next)

        assert response.status_code == 401
        call_next.assert_not_awaited()

    async def test_protected_endpoint_with_access_token_cookie_passes(self):
        req = _make_request(
            f"{API}/users/abc", "GET",
            cookies={"access_token": "valid.cookie.token"},
        )
        call_next = AsyncMock(return_value=JSONResponse(content={}, status_code=200))

        mock_user = MagicMock()
        mock_user.email = "user@example.com"

        with patch("middleware.auth_middleware.token_manager.decode_token", return_value=mock_user):
            response = await self.mw.middleware(req, call_next)

        call_next.assert_awaited_once()
        assert response.status_code == 200

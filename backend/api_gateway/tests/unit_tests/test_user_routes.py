"""Unit tests for user proxy routes — auth requirements and gateway delegation."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse
from httpx import AsyncClient

from tests.constants import TEST_USER_ID, TEST_ADMIN_ID, TEST_API, MOCK_UPSTREAM_RESPONSE_BODY
from tests.conftest import TEST_REGULAR_USER, TEST_ADMIN_USER


# ---------------------------------------------------------------------------
# Public endpoints (no auth needed)
# ---------------------------------------------------------------------------

class TestPublicUserRoutes:
    async def test_register_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.post(f"{TEST_API}/register", json={"email": "a@b.com", "password": "secret"})
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_forgot_password_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.post(f"{TEST_API}/forgot-password", json={"email": "a@b.com"})
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_activate_token_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.post(f"{TEST_API}/activate", json={"token": "mytoken123"})
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_reset_password_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.post(
            f"{TEST_API}/password-reset",
            json={"token": "mytoken123", "new_password": "newpass"},
        )
        mock_forward.assert_awaited_once()
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Login / Logout (token cookie handling)
# ---------------------------------------------------------------------------

class TestLoginRoute:
    async def test_login_returns_200_on_upstream_success(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        """login route does special cookie handling — test that it returns upstream success."""
        from orjson import dumps
        mock_forward.return_value = JSONResponse(
            content={
                "access_token": "tok_access",
                "refresh_token": "tok_refresh",
                "token_type": "bearer",
            },
            status_code=200,
        )
        response = await client.post(
            f"{TEST_API}/login",
            data={"email": "a@b.com", "password": "secret"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200

    async def test_login_returns_upstream_error_unchanged(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        mock_forward.return_value = JSONResponse(
            content={"detail": "Invalid credentials"},
            status_code=401,
        )
        response = await client.post(
            f"{TEST_API}/login",
            data={"email": "a@b.com", "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 401


class TestRefreshRoute:
    async def test_refresh_without_cookie_returns_401(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.post(f"{TEST_API}/refresh")
        assert response.status_code == 401
        mock_forward.assert_not_awaited()

    async def test_refresh_with_cookie_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        mock_forward.return_value = JSONResponse(
            content={"access_token": "new_tok"},
            status_code=200,
        )
        client.cookies.set("refresh_token", "old_refresh_tok")
        response = await client.post(f"{TEST_API}/refresh")
        mock_forward.assert_awaited_once()
        assert response.status_code == 200


    async def test_refresh_sets_the_new_access_and_rotated_refresh_cookies(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        """user-service spends the old refresh token on every refresh; the
        browser must be given the rotated one, or its next refresh presents a
        spent token, reads as theft, and ends every session."""
        mock_forward.return_value = JSONResponse(
            content={
                "access_token": "new_access",
                "token_type": "bearer",
                "token_expiry": 123,
                "refresh_token": "rotated_refresh",
                "refresh_token_expiry": 456,
            },
            status_code=200,
        )
        client.cookies.set("refresh_token", "old_refresh_tok")
        response = await client.post(f"{TEST_API}/refresh")

        assert response.status_code == 200
        assert response.cookies.get("access_token") == "new_access"
        assert response.cookies.get("refresh_token") == "rotated_refresh"
        # The refresh token never travels in a body a script could read.
        assert "refresh_token" not in response.json()
        assert "refresh_token_expiry" not in response.json()

    async def test_refresh_failure_sets_no_cookie(self, client: AsyncClient, mock_forward: AsyncMock):
        mock_forward.return_value = JSONResponse(content={"detail": "reuse detected"}, status_code=401)
        client.cookies.set("refresh_token", "spent")
        response = await client.post(f"{TEST_API}/refresh")
        assert response.status_code == 401
        assert "set-cookie" not in response.headers


class TestSignInCookies:
    async def test_passkey_sign_in_sets_cookies_and_keeps_refresh_out_of_the_body(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        mock_forward.return_value = JSONResponse(
            content={
                "access_token": "admin_access",
                "token_type": "bearer",
                "token_expiry": 123,
                "refresh_token": "admin_refresh",
                "refresh_token_expiry": 456,
                "user_role": "admin",
            },
            status_code=200,
        )
        response = await client.post(
            f"{TEST_API}/login/passkey/verify", json={"challenge_id": "x" * 20, "credential": {}}
        )
        assert response.status_code == 200
        assert response.cookies.get("refresh_token") == "admin_refresh"
        assert response.json()["access_token"] == "admin_access"
        assert "refresh_token" not in response.json()


class TestLogoutRoute:
    async def test_logout_returns_200(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.post(f"{TEST_API}/logout")
        assert response.status_code == 200

    async def test_logout_clears_both_cookies(self, client: AsyncClient, mock_forward: AsyncMock):
        client.cookies.set("refresh_token", "old_refresh")
        client.cookies.set("access_token", "old_access")
        response = await client.post(f"{TEST_API}/logout")
        cleared = response.headers.get_list("set-cookie")
        assert any(c.startswith("access_token=") and "Max-Age=0" in c for c in cleared)
        assert any(c.startswith("refresh_token=") and "Max-Age=0" in c for c in cleared)

    async def test_logout_calls_forward_when_refresh_cookie_present(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        client.cookies.set("refresh_token", "old_refresh")
        await client.post(f"{TEST_API}/logout")
        mock_forward.assert_awaited_once()


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------

class TestAuthenticatedUserRoutes:
    async def test_get_me_calls_forward(self, client: AsyncClient, mock_forward: AsyncMock):
        response = await client.get(f"{TEST_API}/me")
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_get_user_by_id_own_data_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get(f"{TEST_API}/users/{TEST_USER_ID}")
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_get_user_by_id_other_user_returns_403(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        other_id = uuid4()
        response = await client.get(f"{TEST_API}/users/{other_id}")
        assert response.status_code == 403
        mock_forward.assert_not_awaited()

    async def test_update_user_own_data_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.patch(f"{TEST_API}/users/{TEST_USER_ID}", json={"name": "New"})
        mock_forward.assert_awaited_once()

    async def test_delete_user_own_data_calls_forward(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.delete(f"{TEST_API}/users/{TEST_USER_ID}")
        mock_forward.assert_awaited_once()


# ---------------------------------------------------------------------------
# Admin-only endpoints
# ---------------------------------------------------------------------------

class TestAdminUserRoutes:
    async def test_get_all_users_as_admin_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.get(f"{TEST_API}/users")
        mock_forward.assert_awaited_once()
        assert response.status_code == 200

    async def test_get_all_users_as_regular_user_returns_403(
        self, client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await client.get(f"{TEST_API}/users")
        assert response.status_code == 403
        mock_forward.assert_not_awaited()

    async def test_admin_schema_calls_forward(
        self, admin_client: AsyncClient, mock_forward: AsyncMock
    ):
        response = await admin_client.get(f"{TEST_API}/admin/schema/users")
        mock_forward.assert_awaited_once()

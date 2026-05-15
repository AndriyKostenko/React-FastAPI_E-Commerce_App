"""
Route-level tests for user_service endpoints.

Uses httpx.AsyncClient + ASGITransport to send real HTTP requests through
the Fasttest_settings.API application without any live infrastructure:
  - App lifespan is replaced with a no-op (no DB/Redis/RabbitMQ connections).
  - UserService dependency is overridden via app.dependency_overrides.
  - user_events_publisher is patched so no events reach RabbitMQ.

All tests that exercise an error branch configure the mock_route_service
to raise the appropriate exception via .side_effect.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

from exceptions.user_exceptions import (
    UserAlreadyExistsError,
    UserAuthenticationError,
    UserNotFoundError,
)
from shared.shared_instances import test_settings


class TestHealthEndpoint:
    async def test_health_returns_ok(self, client):
        response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "user-service"


class TestRegisterEndpoint:
    async def test_register_success(self, client):
        response = await client.post(f"{test_settings.API}/register", json=test_settings.REGISTER_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "test@example.com"

    async def test_register_duplicate_email_returns_409(self, client, mock_route_service):
        mock_route_service.create_user = AsyncMock(
            side_effect=UserAlreadyExistsError("Email already registered")
        )

        response = await client.post(f"{test_settings.API}/register", json=test_settings.REGISTER_PAYLOAD)

        assert response.status_code == 409

    async def test_register_invalid_payload_returns_422(self, client):
        response = await client.post(f"{test_settings.API}/register", json={"name": "x"})

        assert response.status_code == 422


# ===========================================================================
# POST /activate/{token}
# ===========================================================================


class TestVerifyEmailEndpoint:
    async def test_verify_email_success(self, client):
        response = await client.post(f"{test_settings.API}/activate/valid-token")

        assert response.status_code == 200
        body = response.json()
        assert body["verified"] is True
        assert body["email"] == "test@example.com"

    async def test_verify_email_invalid_token_returns_404(self, client, mock_route_service):
        mock_route_service.verify_email = AsyncMock(
            side_effect=UserNotFoundError("Token invalid or expired")
        )

        response = await client.post(f"{test_settings.API}/activate/bad-token")

        assert response.status_code == 404


# ===========================================================================
# POST /forgot-password
# ===========================================================================


class TestForgotPasswordEndpoint:
    async def test_forgot_password_success(self, client):
        response = await client.post(
            f"{test_settings.API}/forgot-password", params={"email": "test@example.com"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "test@example.com"

    async def test_forgot_password_unknown_email_returns_404(self, client, mock_route_service):
        mock_route_service.request_password_reset = AsyncMock(
            side_effect=UserNotFoundError("No account with that email")
        )

        response = await client.post(
            f"{test_settings.API}/forgot-password", params={"email": "nobody@example.com"}
        )

        assert response.status_code == 404


# ===========================================================================
# POST /password-reset/{token}
# ===========================================================================


class TestResetPasswordEndpoint:
    async def test_reset_password_success(self, client):
        response = await client.post(
            f"{test_settings.API}/password-reset/valid-token",
            json={"email": "test@example.com", "new_password": "newpassword1"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "test@example.com"

    async def test_reset_password_invalid_token_returns_404(self, client, mock_route_service):
        mock_route_service.reset_password_with_token = AsyncMock(
            side_effect=UserNotFoundError("Token invalid or expired")
        )

        response = await client.post(
            f"{test_settings.API}/password-reset/bad-token",
            json={"email": "test@example.com", "new_password": "newpassword1"},
        )

        assert response.status_code == 404


# ===========================================================================
# POST /login
# ===========================================================================


class TestLoginEndpoint:
    async def test_login_success(self, client):
        response = await client.post(f"{test_settings.API}/login", data=test_settings.LOGIN_DATA)

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "access_tok"
        assert body["refresh_token"] == "refresh_tok"
        assert "token_type" in body

    async def test_login_invalid_credentials_returns_401(self, client, mock_route_service):
        mock_route_service.login_user = AsyncMock(
            side_effect=UserAuthenticationError("Invalid credentials")
        )

        response = await client.post(f"{test_settings.API}/login", data=test_settings.LOGIN_DATA)

        assert response.status_code == 401

    async def test_login_missing_fields_returns_422(self, client):
        response = await client.post(f"{test_settings.API}/login", data={"username": "only-username"})

        assert response.status_code == 422


# ===========================================================================
# POST /refresh
# ===========================================================================


class TestRefreshTokenEndpoint:
    async def test_refresh_token_success(self, client):
        response = await client.post(
            f"{test_settings.API}/refresh", json={"refresh_token": "valid-refresh-token"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "new_access_tok"
        assert "token_expiry" in body

    async def test_refresh_token_invalid_returns_401(self, client, mock_route_service):
        mock_route_service.refresh_access_token = AsyncMock(
            side_effect=UserAuthenticationError("Refresh token invalid or expired")
        )

        response = await client.post(
            f"{test_settings.API}/refresh", json={"refresh_token": "expired-token"}
        )

        assert response.status_code == 401


# ===========================================================================
# POST /logout
# ===========================================================================


class TestLogoutEndpoint:
    async def test_logout_success(self, client):
        response = await client.post(
            f"{test_settings.API}/logout", json={"refresh_token": "some-refresh-token"}
        )

        assert response.status_code == 200
        assert response.json()["detail"] == "Logged out successfully"


# ===========================================================================
# GET /me
# ===========================================================================


class TestGetMeEndpoint:
    async def test_get_me_returns_current_user(self, client):
        # get_current_user is overridden in the client fixture to return _CURRENT_USER
        response = await client.get(
            f"{test_settings.API}/me", headers={"Authorization": "Bearer fake-token"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "test@example.com"
        assert body["role"] == "user"


# ===========================================================================
# GET /users/{user_id}
# ===========================================================================


class TestGetUserByIdEndpoint:
    async def test_get_user_by_id_success(self, client):
        response = await client.get(f"{test_settings.API}/users/{test_settings.TEST_USER_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "test@example.com"

    async def test_get_user_by_id_not_found_returns_404(self, client, mock_route_service):
        mock_route_service.get_user_by_id = AsyncMock(
            side_effect=UserNotFoundError("User not found")
        )

        response = await client.get(f"{test_settings.API}/users/{uuid4()}")

        assert response.status_code == 404

    async def test_get_user_by_id_invalid_uuid_returns_422(self, client):
        response = await client.get(f"{test_settings.API}/users/not-a-uuid")

        assert response.status_code == 422


# ===========================================================================
# GET /users
# ===========================================================================


class TestGetAllUsersEndpoint:
    async def test_get_all_users_success(self, client):
        response = await client.get(f"{test_settings.API}/users")

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert body[0]["email"] == "test@example.com"

    async def test_get_all_users_none_found_returns_404(self, client, mock_route_service):
        mock_route_service.get_all_users = AsyncMock(
            side_effect=UserNotFoundError("No users found")
        )

        response = await client.get(f"{test_settings.API}/users")

        assert response.status_code == 404

    async def test_get_all_users_pagination_params(self, client):
        response = await client.get(f"{test_settings.API}/users", params={"offset": 0, "limit": 5})

        assert response.status_code == 200

    async def test_get_all_users_invalid_limit_returns_422(self, client):
        # limit must be > 0 and <= 100
        response = await client.get(f"{test_settings.API}/users", params={"limit": 0})

        assert response.status_code == 422


# ===========================================================================
# PATCH /users/{user_id}
# ===========================================================================


class TestUpdateUserEndpoint:
    async def test_update_user_success(self, client):
        response = await client.patch(
            f"{test_settings.API}/users/{test_settings.TEST_USER_ID}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "test@example.com"

    async def test_update_user_not_found_returns_404(self, client, mock_route_service):
        mock_route_service.update_user_basic_info = AsyncMock(
            side_effect=UserNotFoundError("User not found")
        )

        response = await client.patch(
            f"{test_settings.API}/users/{uuid4()}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 404


# ===========================================================================
# DELETE /users/{user_id}
# ===========================================================================


class TestDeleteUserEndpoint:
    async def test_delete_user_success(self, client):
        response = await client.delete(f"{test_settings.API}/users/{test_settings.TEST_USER_ID}")

        assert response.status_code == 200
        assert response.json()["detail"] == "User deleted successfully"

    async def test_delete_user_not_found_returns_404(self, client, mock_route_service):
        mock_route_service.delete_user_by_id = AsyncMock(
            side_effect=UserNotFoundError("User not found")
        )

        response = await client.delete(f"{test_settings.API}/users/{uuid4()}")

        assert response.status_code == 404


# ===========================================================================
# GET /admin/schema/users
# ===========================================================================


class TestAdminSchemaEndpoint:
    async def test_admin_schema_returns_fields(self, client):
        response = await client.get(f"{test_settings.API}/admin/schema/users")

        assert response.status_code == 200
        body = response.json()
        assert "fields" in body
        assert isinstance(body["fields"], list)



# pytestmark = pytest.mark.asyncio(scope="package")


# # using AsyncClient to work with async calls to db and async sqlalchemy

# async def test_user_routes():
#     async with AsyncClient(transport=ASGITransport(app), base_url="http://127.0.0.1") as client:
#         # creating database models in tests database
#         await init_db()

#         response_1 = await client.post('/register', json={'name': 'Andriy Kostenko',
#                                                           'email': 'a.kostenkouk@gmail.com',
#                                                           'password': '12345678'})
#         response_2 = await client.post('/register', json={'name': 'Andriy Kostenko',
#                                                           'email': 'a.kostenkouk@gmail.com',
#                                                           'password': '12345678'})
#         response_3 = await client.post('/register', json={'name': 'Andriy Kostenko',
#                                                           'email': 1,
#                                                           'password': '12345678'})

#         # using 'username' field instead of 'email' field because it takes from OAuth2PasswordRequestForm
#         response_4 = await client.post('/login', data={'username': 'a.kostenkouk@gmail.com',
#                                                        'password': '12345678'})
#         response_5 = await client.post('/login', data={'username': 'a.kostenkouk@gmail.com',
#                                                        'password': 'anfjdjfdkdfj111111111111'})

#         assert response_1.status_code == status.HTTP_201_CREATED
#         assert response_2.status_code == status.HTTP_409_CONFLICT
#         assert response_3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
#         assert response_4.status_code == status.HTTP_200_OK
#         assert response_5.status_code == status.HTTP_401_UNAUTHORIZED

#         # cleaning tests database
#         await drop_all_tables()

"""
Integration tests for user_service HTTP routes.

Uses a real PostgreSQL test datatest_settings.API (USER_SERVICE_TEST_DB) and real
PasswordManager / TokenManager.  Redis and RabbitMQ are mocked.

Each test class maps to one route group.  The DB is truncated between
every test function so every test starts with a fully empty users table.

Module-level helper coroutines (_register, _activate, _login, …) keep
test methods short and readable without tying state to fixture order.
"""
from httpx import AsyncClient
from fastapi import status

from shared.shared_instances import test_settings

# ---------------------------------------------------------------------------
# Module-level helpers — call inside test methods to compose state
# ---------------------------------------------------------------------------

async def _register(client: AsyncClient,
                    *args,
                    email: str = test_settings.TEST_EMAIL,
                    password: str = test_settings.TEST_PASSWORD,
                    name: str = test_settings.TEST_NAME,):
    return await client.post(
        f"{test_settings.API}/register",
        json={"name": name, "email": email, "password": password},
    )


async def _activate(client: AsyncClient, publisher):
    """Capture the verification token from the mocked publisher and activate."""
    token = publisher.publish_user_registered.call_args.args[1]
    return await client.post(f"{test_settings.API}/activate/{token}")


async def _login(
    client: AsyncClient,
    *,
    email: str = test_settings.TEST_EMAIL,
    password: str = test_settings.TEST_PASSWORD):
    return await client.post(
        f"{test_settings.API}/login",
        data={"username": email, "password": password},
    )


async def _setup_verified_user(
    client: AsyncClient,
    publisher,
    *,
    email: str = test_settings.TEST_EMAIL,
    password: str = test_settings.TEST_PASSWORD,
    name: str = test_settings.TEST_NAME,) -> dict[str, str|int]:
    """Register + activate; returns the register response body."""
    reg = await _register(client, email=email, password=password, name=name)
    await _activate(client, publisher)
    return reg.json()


async def _setup_authenticated_user(
    client: AsyncClient,
    publisher,
    *,
    email: str = test_settings.TEST_EMAIL,
    password: str = test_settings.TEST_PASSWORD,
    name: str = test_settings.TEST_NAME,
) -> dict[str, str|int]:
    """Register + activate + login; returns the login response body (tokens + user data)."""
    await _setup_verified_user(client, publisher, email=email, password=password, name=name)
    login = await _login(client, email=email, password=password)
    return login.json()


# ===========================================================================
# GET /health
# ===========================================================================


class TestHealthEndpoint:
    async def test_health_returns_ok(self, integration_client: AsyncClient):
        response = await integration_client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "user-service"


# ===========================================================================
# POST /api/v1/register
# ===========================================================================
class TestUserRegister:

    async def test_register_new_user_returns_201_and_user_data(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        response = await _register(integration_client)
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["email"] == test_settings.TEST_EMAIL
        assert body["name"] == test_settings.TEST_NAME
        assert "id" in body

    async def test_register_publishes_verification_event(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _register(integration_client)
        mock_user_events_publisher.publish_user_registered.assert_awaited_once()
        # first positional arg is the email
        assert mock_user_events_publisher.publish_user_registered.call_args.args[0] == test_settings.TEST_EMAIL

    async def test_register_duplicate_email_returns_409(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _register(integration_client)
        duplicate = await _register(integration_client)
        assert duplicate.status_code == status.HTTP_409_CONFLICT

    async def test_register_type_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/register",
            json={"name": test_settings.TEST_NAME, "email": 1, "password": test_settings.TEST_PASSWORD},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_register_missing_password_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/register",
            json={"name": test_settings.TEST_NAME, "email": test_settings.TEST_EMAIL},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_register_short_password_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/register",
            json={"name": test_settings.TEST_NAME, "email": test_settings.TEST_EMAIL, "password": "short"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ===========================================================================
# POST /api/v1/activate/{token}
# ===========================================================================


class TestActivateEmailEndpoint:
    async def test_activate_valid_token_returns_200_and_verified_flag(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _register(integration_client)
        response = await _activate(integration_client, mock_user_events_publisher)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["verified"] is True
        assert body["email"] == test_settings.TEST_EMAIL

    async def test_activate_publishes_email_verified_event(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _register(integration_client)
        await _activate(integration_client, mock_user_events_publisher)
        mock_user_events_publisher.publish_email_verified.assert_awaited_once()

    async def test_activate_invalid_token_returns_401(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(f"{test_settings.API}/activate/this-is-not-a-valid-jwt")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# POST /api/v1/login
# ===========================================================================


class TestLoginEndpoint:
    async def test_login_success_returns_tokens_and_user_data(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _setup_verified_user(integration_client, mock_user_events_publisher)
        response = await _login(integration_client)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["user_email"] == test_settings.TEST_EMAIL

    async def test_login_wrong_password_returns_401(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _setup_verified_user(integration_client, mock_user_events_publisher)
        response = await integration_client.post(
            f"{test_settings.API}/login",
            data={"username": test_settings.TEST_EMAIL, "password": "WrongPassword!"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_unknown_email_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/login",
            data={"username": "nobody@example.com", "password": test_settings.TEST_PASSWORD},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_login_unverified_user_returns_401(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _register(integration_client)  # register but do NOT activate
        response = await _login(integration_client)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_missing_password_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/login",
            data={"username": test_settings.TEST_EMAIL},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ===========================================================================
# POST /api/v1/refresh
# ===========================================================================


class TestRefreshTokenEndpoint:
    async def test_refresh_returns_new_access_token(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        login_data = await _setup_authenticated_user(integration_client, mock_user_events_publisher)
        response = await integration_client.post(
            f"{test_settings.API}/refresh",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "access_token" in body
        assert "token_expiry" in body

    async def test_refresh_invalid_token_returns_401(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/refresh",
            json={"refresh_token": "not-a-real-token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# POST /api/v1/logout
# ===========================================================================


class TestLogoutEndpoint:
    async def test_logout_success_returns_200(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        login_data = await _setup_authenticated_user(integration_client, mock_user_events_publisher)
        response = await integration_client.post(
            f"{test_settings.API}/logout",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["detail"] == "Logged out successfully"


# ===========================================================================
# GET /api/v1/me
# ===========================================================================


class TestGetMeEndpoint:
    async def test_get_me_returns_current_user_data(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        login_data = await _setup_authenticated_user(integration_client, mock_user_events_publisher)
        response = await integration_client.get(
            f"{test_settings.API}/me",
            headers={"Authorization": f"Bearer {login_data['access_token']}"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["email"] == test_settings.TEST_EMAIL
        assert body["role"] == "user"

    async def test_get_me_without_token_returns_401(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.get(f"{test_settings.API}/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_me_with_invalid_token_returns_401(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.get(
            f"{test_settings.API}/me",
            headers={"Authorization": "Bearer this.is.invalid"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# POST /api/v1/forgot-password
# ===========================================================================


class TestForgotPasswordEndpoint:
    async def test_forgot_password_known_email_returns_200(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _setup_verified_user(integration_client, mock_user_events_publisher)
        response = await integration_client.post(
            f"{test_settings.API}/forgot-password",
            params={"email": test_settings.TEST_EMAIL},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["email"] == test_settings.TEST_EMAIL

    async def test_forgot_password_publishes_reset_event(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _setup_verified_user(integration_client, mock_user_events_publisher)
        await integration_client.post(
            f"{test_settings.API}/forgot-password",
            params={"email": test_settings.TEST_EMAIL},
        )
        mock_user_events_publisher.publish_password_reset_request.assert_awaited_once()

    async def test_forgot_password_unknown_email_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/forgot-password",
            params={"email": "nobody@example.com"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# POST /api/v1/password-reset/{token}
# ===========================================================================


class TestResetPasswordEndpoint:
    async def test_reset_password_with_valid_token_returns_200(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _setup_verified_user(integration_client, mock_user_events_publisher)
        await integration_client.post(f"{test_settings.API}/forgot-password", params={"email": test_settings.TEST_EMAIL})
        reset_token = mock_user_events_publisher.publish_password_reset_request.call_args.kwargs["reset_token"]

        response = await integration_client.post(
            f"{test_settings.API}/password-reset/{reset_token}",
            json={"email": test_settings.TEST_EMAIL, "new_password": "NewPassword123!"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["email"] == test_settings.TEST_EMAIL

    async def test_reset_password_new_credentials_work_on_login(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        new_password = "NewPassword123!"
        await _setup_verified_user(integration_client, mock_user_events_publisher)
        await integration_client.post(f"{test_settings.API}/forgot-password", params={"email": test_settings.TEST_EMAIL})
        reset_token = mock_user_events_publisher.publish_password_reset_request.call_args.kwargs["reset_token"]

        await integration_client.post(
            f"{test_settings.API}/password-reset/{reset_token}",
            json={"email": test_settings.TEST_EMAIL, "new_password": new_password},
        )
        login_resp = await _login(integration_client, password=new_password)
        assert login_resp.status_code == status.HTTP_200_OK

    async def test_reset_password_old_password_no_longer_works(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        new_password = "NewPassword123!"
        await _setup_verified_user(integration_client, mock_user_events_publisher)
        await integration_client.post(f"{test_settings.API}/forgot-password", params={"email": test_settings.TEST_EMAIL})
        reset_token = mock_user_events_publisher.publish_password_reset_request.call_args.kwargs["reset_token"]

        await integration_client.post(
            f"{test_settings.API}/password-reset/{reset_token}",
            json={"email": test_settings.TEST_EMAIL, "new_password": new_password},
        )
        old_login = await _login(integration_client, password=test_settings.TEST_PASSWORD)
        assert old_login.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_reset_password_invalid_token_returns_401(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/password-reset/invalid-token",
            json={"email": test_settings.TEST_EMAIL, "new_password": "NewPassword123!"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# GET /api/v1/users/{user_id}
# ===========================================================================


class TestGetUserByIdEndpoint:
    async def test_get_user_by_id_returns_200_and_user_data(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        user_data = await _setup_verified_user(integration_client, mock_user_events_publisher)
        response = await integration_client.get(f"{test_settings.API}/users/{user_data['id']}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["email"] == test_settings.TEST_EMAIL
        assert body["id"] == user_data["id"]

    async def test_get_user_by_unknown_id_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.get(
            f"{test_settings.API}/users/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_user_by_invalid_uuid_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.get(f"{test_settings.API}/users/not-a-uuid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ===========================================================================
# GET /api/v1/users
# ===========================================================================


class TestGetAllUsersEndpoint:
    async def test_get_all_users_returns_list_with_one_user(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        await _setup_verified_user(integration_client, mock_user_events_publisher)
        response = await integration_client.get(f"{test_settings.API}/users")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["email"] == test_settings.TEST_EMAIL

    async def test_get_all_users_empty_db_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.get(f"{test_settings.API}/users")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_all_users_pagination_returns_correct_pages(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        # Register and activate two separate users
        for email in ("user1@example.com", "user2@example.com"):
            await _register(integration_client, email=email)
            token = mock_user_events_publisher.publish_user_registered.call_args.args[1]
            await integration_client.post(f"{test_settings.API}/activate/{token}")

        page_1 = await integration_client.get(f"{test_settings.API}/users", params={"offset": 0, "limit": 1})
        page_2 = await integration_client.get(f"{test_settings.API}/users", params={"offset": 1, "limit": 1})

        assert page_1.status_code == status.HTTP_200_OK
        assert page_2.status_code == status.HTTP_200_OK
        assert len(page_1.json()) == 1
        assert len(page_2.json()) == 1
        assert page_1.json()[0]["email"] != page_2.json()[0]["email"]

    async def test_get_all_users_invalid_limit_returns_422(
        self, integration_client: AsyncClient
    ):
        # limit must be > 0 and <= 100
        response = await integration_client.get(f"{test_settings.API}/users", params={"limit": 0})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ===========================================================================
# PATCH /api/v1/users/{user_id}
# ===========================================================================


class TestUpdateUserEndpoint:
    async def test_update_user_name_returns_200_and_new_name(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        user_data = await _setup_verified_user(integration_client, mock_user_events_publisher)
        response = await integration_client.patch(
            f"{test_settings.API}/users/{user_data['id']}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["name"] == "Updated Name"
        assert body["email"] == test_settings.TEST_EMAIL

    async def test_update_unknown_user_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.patch(
            f"{test_settings.API}/users/00000000-0000-0000-0000-000000000000",
            json={"name": "Ghost"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_user_name_too_short_returns_422(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        user_data = await _setup_verified_user(integration_client, mock_user_events_publisher)
        response = await integration_client.patch(
            f"{test_settings.API}/users/{user_data['id']}",
            json={"name": "x"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ===========================================================================
# DELETE /api/v1/users/{user_id}
# ===========================================================================


class TestDeleteUserEndpoint:
    async def test_delete_user_returns_200(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        user_data = await _setup_verified_user(integration_client, mock_user_events_publisher)
        response = await integration_client.delete(f"{test_settings.API}/users/{user_data['id']}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["detail"] == "User deleted successfully"

    async def test_deleted_user_is_no_longer_retrievable(
        self, integration_client: AsyncClient, mock_user_events_publisher
    ):
        user_data = await _setup_verified_user(integration_client, mock_user_events_publisher)
        await integration_client.delete(f"{test_settings.API}/users/{user_data['id']}")
        get_response = await integration_client.get(f"{test_settings.API}/users/{user_data['id']}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_unknown_user_returns_404(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.delete(
            f"{test_settings.API}/users/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# GET /api/v1/admin/schema/users
# ===========================================================================


class TestAdminSchemaEndpoint:
    async def test_admin_schema_returns_fields_list(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.get(f"{test_settings.API}/admin/schema/users")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "fields" in body
        assert isinstance(body["fields"], list)
        assert len(body["fields"]) > 0

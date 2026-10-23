"""
Integration tests for user_service HTTP routes.

Uses a real PostgreSQL test datatest_settings.API (USER_SERVICE_TEST_DB) and real
PasswordManager / TokenManager.  Redis and RabbitMQ are mocked.

Each test class maps to one route group.  The DB is truncated between
every test function so every test starts with a fully empty users table.

Module-level helper coroutines (_register, _activate, _login, …) keep
test methods short and readable without tying state to fixture order.
"""
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient, Response
from fastapi import status

from settings import get_test_settings
from contracts.event_enums import UserEvents
from tests.conftest import SIGNING_KEYS, as_gateway
from infrastructure.testing.signing_keys import EphemeralSigningKeys
from models.user_models import User
from contracts.auth import AuthMethod
from service_layer.session_issuer import IssuedSession, SessionIssuer

test_settings = get_test_settings()

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
        json={"name": name, "email": email, "password": password,
              "captcha_token": test_settings.CAPTCHA_TOKEN},
    )


async def _activate(client: AsyncClient, get_outbox_event: Callable[[str], Awaitable[dict[str, Any] | None]]):
    """Read the verification token from the outbox and activate the user."""
    payload = await get_outbox_event(UserEvents.USER_REGISTERED)
    assert payload is not None, "Expected a user.registered outbox event"
    token = payload["token"]
    return await client.post(f"{test_settings.API}/activate", json={"token": token})


async def _login(
    client: AsyncClient,
    *,
    email: str = test_settings.TEST_EMAIL,
    password: str = test_settings.TEST_PASSWORD):
    return await client.post(
        f"{test_settings.API}/login",
        data={"username": email, "password": password, "captcha_token": test_settings.CAPTCHA_TOKEN},
    )


async def _setup_verified_user(
    client: AsyncClient,
    get_outbox_event: Callable[[str], Awaitable[dict[str, Any] | None]],
    *,
    email: str = test_settings.TEST_EMAIL,
    password: str = test_settings.TEST_PASSWORD,
    name: str = test_settings.TEST_NAME,) -> dict[str, str|int]:
    """Register + activate; returns the new account's id and email.

    Registration no longer answers with the account (it says the same thing
    whether or not the email was taken), so the id is read from the
    verification event it writes.
    """
    await _register(client, email=email, password=password, name=name)
    registered = await get_outbox_event(UserEvents.USER_REGISTERED)
    assert registered is not None, "Expected a user.registered outbox event"
    await _activate(client, get_outbox_event)
    return {"id": str(registered["user_id"]), "email": email}


async def _setup_authenticated_user(
    client: AsyncClient,
    get_outbox_event: Callable[[str], Awaitable[dict[str, Any] | None]],
    *,
    email: str = test_settings.TEST_EMAIL,
    password: str = test_settings.TEST_PASSWORD,
    name: str = test_settings.TEST_NAME,
) -> dict[str, str|int]:
    """Register + activate + login; returns the login response body (tokens + user data)."""
    await _setup_verified_user(client, get_outbox_event, email=email, password=password, name=name)
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

    async def test_register_new_user_is_accepted_without_echoing_the_account(
        self, integration_client: AsyncClient
    ):
        response = await _register(integration_client)
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json() == {"detail": "Check your email to finish creating your account."}

    async def test_register_creates_verification_outbox_event(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _register(integration_client)
        payload = await get_outbox_event(UserEvents.USER_REGISTERED)
        assert payload is not None
        assert payload["user_email"] == test_settings.TEST_EMAIL
        assert "token" in payload

    async def test_a_taken_email_gets_the_same_answer_as_a_new_one(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        """"Already registered" would let anyone test which addresses are customers."""
        await _setup_verified_user(integration_client, get_outbox_event)
        again = await _register(integration_client, password="Another-password-1")
        assert again.status_code == status.HTTP_202_ACCEPTED
        assert again.json() == {"detail": "Check your email to finish creating your account."}

        # The owner is told by email instead, and their password is unchanged.
        notice = await get_outbox_event(UserEvents.USER_REGISTRATION_EXISTING)
        assert notice is not None
        assert notice["user_email"] == test_settings.TEST_EMAIL
        assert (await _login(integration_client)).status_code == status.HTTP_200_OK
        assert (await _login(integration_client, password="Another-password-1")).status_code == status.HTTP_401_UNAUTHORIZED

    async def test_the_owner_is_mailed_once_per_interval(
        self, integration_client: AsyncClient, get_outbox_event, count_outbox_events
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        for _ in range(3):
            assert (await _register(integration_client)).status_code == status.HTTP_202_ACCEPTED
        assert await count_outbox_events(UserEvents.USER_REGISTRATION_EXISTING) == 1

    async def test_registering_again_before_verifying_sends_a_fresh_link(
        self, integration_client: AsyncClient, count_outbox_events
    ):
        await _register(integration_client)
        await _register(integration_client)
        # The first link may be lost; the second registration sends a new one.
        assert await count_outbox_events(UserEvents.USER_REGISTERED) == 2
        assert await count_outbox_events(UserEvents.USER_REGISTRATION_EXISTING) == 0

    async def test_register_without_the_verification_creates_nothing(
        self, integration_client: AsyncClient, count_outbox_events
    ):
        for captcha in ({}, {"captcha_token": "forged-token"}):
            response = await integration_client.post(
                f"{test_settings.API}/register",
                json={"name": test_settings.TEST_NAME, "email": test_settings.TEST_EMAIL,
                      "password": test_settings.TEST_PASSWORD, **captcha},
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert response.json()["detail"] == "Please complete the verification and try again."
        assert await count_outbox_events(UserEvents.USER_REGISTERED) == 0

    async def test_a_disposable_address_is_refused_under_the_email_field(
        self, integration_client: AsyncClient, count_outbox_events
    ):
        response = await _register(integration_client, email="someone@mailinator.com")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["errors"] == [{
            "field": "email",
            "message": "Disposable email addresses can't be used. Please use a permanent address.",
        }]
        assert await count_outbox_events(UserEvents.USER_REGISTERED) == 0

    async def test_register_type_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/register",
            json={"name": test_settings.TEST_NAME, "email": 1, "password": test_settings.TEST_PASSWORD},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_register_missing_password_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/register",
            json={"name": test_settings.TEST_NAME, "email": test_settings.TEST_EMAIL},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_register_short_password_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/register",
            json={"name": test_settings.TEST_NAME, "email": test_settings.TEST_EMAIL, "password": "short"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ===========================================================================
# POST /api/v1/activate
# ===========================================================================


class TestActivateEmailEndpoint:
    async def test_activate_valid_token_returns_200_and_verified_flag(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _register(integration_client)
        response = await _activate(integration_client, get_outbox_event)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["verified"] is True
        assert body["email"] == test_settings.TEST_EMAIL

    async def test_activate_creates_email_verified_outbox_event(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _register(integration_client)
        await _activate(integration_client, get_outbox_event)
        payload = await get_outbox_event(UserEvents.USER_EMAIL_VERIFIED)
        assert payload is not None
        assert payload["user_email"] == test_settings.TEST_EMAIL

    async def test_activate_invalid_token_returns_401(
        self, integration_client: AsyncClient
    ):
        # Long enough to clear the schema's length floor, so the 401 comes
        # from token verification rather than request validation.
        response = await integration_client.post(
            f"{test_settings.API}/activate",
            json={"token": "not-a-valid-jwt-but-long-enough-to-pass-validation"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# POST /api/v1/login
# ===========================================================================


class TestLoginEndpoint:
    async def test_login_success_returns_tokens_and_user_data(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        response = await _login(integration_client)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["user_email"] == test_settings.TEST_EMAIL

    async def test_login_creates_login_outbox_event(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        await _login(integration_client)
        payload = await get_outbox_event(UserEvents.USER_LOGGED_IN)
        assert payload is not None
        assert payload["user_email"] == test_settings.TEST_EMAIL

    async def test_login_wrong_password_returns_401(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        response = await integration_client.post(
            f"{test_settings.API}/login",
            data={"username": test_settings.TEST_EMAIL, "password": "WrongPassword!", "captcha_token": test_settings.CAPTCHA_TOKEN},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_unknown_email_is_indistinguishable_from_wrong_password(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/login",
            data={"username": "nobody@example.com", "password": test_settings.TEST_PASSWORD, "captcha_token": test_settings.CAPTCHA_TOKEN},
        )
        # A 404 here would let anyone enumerate which addresses hold an
        # account, so an unknown address gets the same 401 and the same
        # message as a wrong password.
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Incorrect email or password"

    async def test_login_unverified_user_returns_401(
        self, integration_client: AsyncClient
    ):
        await _register(integration_client)  # register but do NOT activate
        response = await _login(integration_client)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_without_the_verification_is_refused_before_the_password_is_checked(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        response = await integration_client.post(
            f"{test_settings.API}/login",
            data={"username": test_settings.TEST_EMAIL, "password": test_settings.TEST_PASSWORD},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Please complete the verification and try again."

    async def test_login_missing_password_returns_422(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/login",
            data={"username": test_settings.TEST_EMAIL},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ===========================================================================
# POST /api/v1/refresh
# ===========================================================================


class TestRefreshTokenEndpoint:
    async def test_refresh_returns_new_access_token(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        login_data = await _setup_authenticated_user(integration_client, get_outbox_event)
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

    async def test_replayed_refresh_token_revokes_without_locking_the_user_out(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        """
        Replaying a spent refresh token must end every session — and the user
        must still be able to sign in again afterwards.

        The session-generation bump used to be rolled back with the 401 while
        the new generation stayed published to the gateway, so every later
        login minted a token from the old generation that the gateway refused.
        """
        login_data = await _setup_authenticated_user(integration_client, get_outbox_event)
        spent = login_data["refresh_token"]
        rotated = await integration_client.post(f"{test_settings.API}/refresh", json={"refresh_token": spent})
        assert rotated.status_code == status.HTTP_200_OK

        replay = await integration_client.post(f"{test_settings.API}/refresh", json={"refresh_token": spent})
        assert replay.status_code == status.HTTP_401_UNAUTHORIZED

        # The whole family is gone, including the token rotation just handed out.
        family = await integration_client.post(
            f"{test_settings.API}/refresh", json={"refresh_token": rotated.json()["refresh_token"]}
        )
        assert family.status_code == status.HTTP_401_UNAUTHORIZED

        # A fresh sign-in carries the bumped generation, so the gateway accepts it
        # and its refresh token is usable.
        relogin = await _login(integration_client)
        assert relogin.status_code == status.HTTP_200_OK
        claims = SIGNING_KEYS.user_token_verifier().decode(relogin.json()["access_token"])
        # Advanced past the original generation (each replay above bumps it).
        assert (claims.token_version or 0) > 1
        # Refresh only succeeds when the token's generation equals the database's,
        # so this is what proves the bump was persisted, not rolled back.
        again = await integration_client.post(
            f"{test_settings.API}/refresh", json={"refresh_token": relogin.json()["refresh_token"]}
        )
        assert again.status_code == status.HTTP_200_OK


# ===========================================================================
# POST /api/v1/logout
# ===========================================================================


class TestLogoutEndpoint:
    async def test_logout_success_returns_200(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        login_data = await _setup_authenticated_user(integration_client, get_outbox_event)
        # No access token: the refresh token itself proves which session ends,
        # so a sign-out still works after the access token has expired.
        response = await integration_client.post(
            f"{test_settings.API}/logout",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["detail"] == "Logged out successfully"

        # Revoked: it no longer refreshes.
        refresh = await integration_client.post(
            f"{test_settings.API}/refresh",
            json={"refresh_token": login_data["refresh_token"]},
        )
        assert refresh.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_logout_with_a_token_that_does_not_verify_returns_200(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/logout",
            json={"refresh_token": "not-a-refresh-token"},
        )
        assert response.status_code == status.HTTP_200_OK


async def _refresh(client: AsyncClient, refresh_token: str) -> Response:
    return await client.post(f"{test_settings.API}/refresh", json={"refresh_token": refresh_token})


async def _logout(client: AsyncClient, refresh_token: str) -> Response:
    return await client.post(f"{test_settings.API}/logout", json={"refresh_token": refresh_token})


class TestSignOutRacingRefresh:
    """
    A page can refresh its session at the moment the user signs out.

    The sign-out used to delete the token outright, so a refresh arriving just
    after it read the missing token as a stolen one and ended every session the
    user had. And a refresh finishing just before it left the token it issued
    live, with no one holding it. Either order must end this session only.
    """

    async def test_a_refresh_after_the_sign_out_leaves_other_sessions_alone(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        login_data = await _setup_authenticated_user(integration_client, get_outbox_event)
        signed_out = str(login_data["refresh_token"])
        other_device = (await _login(integration_client)).json()

        assert (await _logout(integration_client, signed_out)).status_code == status.HTTP_200_OK
        # Two late requests from the signed-out page: neither is read as theft.
        for _ in range(2):
            late = await _refresh(integration_client, signed_out)
            assert late.status_code == status.HTTP_401_UNAUTHORIZED
            assert late.json()["detail"] == "Session signed out"

        # Refresh succeeds only while the generation is unchanged, so this
        # proves no session-wide revocation ran.
        assert (await _refresh(integration_client, other_device["refresh_token"])).status_code == status.HTTP_200_OK

    async def test_a_sign_out_with_the_token_a_refresh_just_spent_ends_the_new_one(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        login_data = await _setup_authenticated_user(integration_client, get_outbox_event)
        spent = str(login_data["refresh_token"])
        other_device = (await _login(integration_client)).json()

        rotated = await _refresh(integration_client, spent)
        assert rotated.status_code == status.HTTP_200_OK
        # The page signed out with the token it had, before the refresh's
        # answer reached it.
        assert (await _logout(integration_client, spent)).status_code == status.HTTP_200_OK

        orphan = await _refresh(integration_client, rotated.json()["refresh_token"])
        assert orphan.status_code == status.HTTP_401_UNAUTHORIZED
        assert orphan.json()["detail"] == "Session signed out"
        assert (await _refresh(integration_client, other_device["refresh_token"])).status_code == status.HTTP_200_OK

    @pytest.mark.parametrize("sign_out_lands", ["before_the_link", "after_the_link"])
    async def test_a_sign_out_in_the_middle_of_a_refresh_ends_the_token_it_issues(
        self, integration_client: AsyncClient, get_outbox_event, monkeypatch: pytest.MonkeyPatch, sign_out_lands: str
    ):
        """
        The refresh has already spent the old token when the sign-out runs.

        "before_the_link": the sign-out finds no link to follow, so the
        refresh must notice the sign-out itself. "after_the_link": the
        sign-out follows the link and ends the new token.
        """
        login_data = await _setup_authenticated_user(integration_client, get_outbox_event)
        spent = str(login_data["refresh_token"])
        other_device = (await _login(integration_client)).json()

        original_issue = SessionIssuer.issue
        issued: list[IssuedSession] = []

        async def issue_with_a_sign_out(
            issuer: SessionIssuer, user: User, methods: list[AuthMethod], rotated_from: str | None = None
        ) -> IssuedSession:
            if rotated_from != SessionIssuer.token_hash(spent):
                return await original_issue(issuer, user, methods, rotated_from)
            if sign_out_lands == "before_the_link":
                await _logout(integration_client, spent)
            session = await original_issue(issuer, user, methods, rotated_from)
            issued.append(session)
            if sign_out_lands == "after_the_link":
                await _logout(integration_client, spent)
            return session

        monkeypatch.setattr(SessionIssuer, "issue", issue_with_a_sign_out)

        refresh = await _refresh(integration_client, spent)
        assert refresh.status_code == status.HTTP_401_UNAUTHORIZED
        assert refresh.json()["detail"] == "Session signed out"
        # The token the refresh minted never reached anyone, and is dead.
        assert len(issued) == 1
        assert (await _refresh(integration_client, issued[0].refresh_token)).status_code == status.HTTP_401_UNAUTHORIZED
        assert (await _refresh(integration_client, other_device["refresh_token"])).status_code == status.HTTP_200_OK


# ===========================================================================
# GET /api/v1/me
# ===========================================================================


class TestGetMeEndpoint:
    async def test_get_me_returns_current_user_data(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        login_data = await _setup_authenticated_user(integration_client, get_outbox_event)
        response = await integration_client.get(
            f"{test_settings.API}/me",
            headers=as_gateway(login_data["access_token"], "GET", f"{test_settings.API}/me"),
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

    async def test_get_me_with_forged_assertion_returns_401(
        self, integration_client: AsyncClient
    ):
        # Signed by a key the service does not trust: what reaching the
        # service directly and claiming to be someone looks like now.
        forged = EphemeralSigningKeys().caller_headers(
            "GET", f"{test_settings.API}/me", user_id=test_settings.TEST_USER_ID
        )
        response = await integration_client.get(f"{test_settings.API}/me", headers=forged)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_me_ignores_a_bearer_token_sent_directly(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        # The service no longer reads tokens; only the gateway's assertion counts.
        login_data = await _setup_authenticated_user(integration_client, get_outbox_event)
        response = await integration_client.get(
            f"{test_settings.API}/me",
            headers={"Authorization": f"Bearer {login_data['access_token']}"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# POST /api/v1/forgot-password
# ===========================================================================


class TestForgotPasswordEndpoint:
    async def test_forgot_password_known_email_returns_200(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        response = await integration_client.post(
            f"{test_settings.API}/forgot-password",
            json={"email": test_settings.TEST_EMAIL, "captcha_token": test_settings.CAPTCHA_TOKEN},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["email"] == test_settings.TEST_EMAIL

    async def test_forgot_password_creates_reset_request_outbox_event(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        await integration_client.post(
            f"{test_settings.API}/forgot-password",
            json={"email": test_settings.TEST_EMAIL, "captcha_token": test_settings.CAPTCHA_TOKEN},
        )
        payload = await get_outbox_event(UserEvents.USER_PASSWORD_RESET_REQUEST)
        assert payload is not None
        assert payload["user_email"] == test_settings.TEST_EMAIL
        assert "reset_token" in payload

    async def test_forgot_password_unknown_email_is_indistinguishable(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        response = await integration_client.post(
            f"{test_settings.API}/forgot-password",
            json={"email": "nobody@example.com", "captcha_token": test_settings.CAPTCHA_TOKEN},
        )
        # Answering 404 here would let anyone test which addresses hold an
        # account, so an unknown address gets the same reply as a known one
        # and no reset event is written.
        assert response.status_code == status.HTTP_200_OK
        assert await get_outbox_event(UserEvents.USER_PASSWORD_RESET_REQUEST) is None

    async def test_forgot_password_without_the_verification_sends_nothing(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        response = await integration_client.post(
            f"{test_settings.API}/forgot-password", json={"email": test_settings.TEST_EMAIL}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert await get_outbox_event(UserEvents.USER_PASSWORD_RESET_REQUEST) is None


# ===========================================================================
# POST /api/v1/password-reset
# ===========================================================================


class TestResetPasswordEndpoint:
    async def _get_reset_token(self, get_outbox_event) -> str:
        payload = await get_outbox_event(UserEvents.USER_PASSWORD_RESET_REQUEST)
        assert payload is not None, "Expected a password reset request outbox event"
        return payload["reset_token"]

    async def test_reset_password_with_valid_token_returns_200(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        await integration_client.post(f"{test_settings.API}/forgot-password", json={"email": test_settings.TEST_EMAIL, "captcha_token": test_settings.CAPTCHA_TOKEN})
        reset_token = await self._get_reset_token(get_outbox_event)

        response = await integration_client.post(
            f"{test_settings.API}/password-reset",
            json={"token": reset_token, "new_password": "NewPassword123!"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["email"] == test_settings.TEST_EMAIL

    async def test_reset_password_creates_reset_success_outbox_event(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        await integration_client.post(f"{test_settings.API}/forgot-password", json={"email": test_settings.TEST_EMAIL, "captcha_token": test_settings.CAPTCHA_TOKEN})
        reset_token = await self._get_reset_token(get_outbox_event)

        await integration_client.post(
            f"{test_settings.API}/password-reset",
            json={"token": reset_token, "new_password": "NewPassword123!"},
        )
        payload = await get_outbox_event(UserEvents.USER_PASSWORD_RESET_SUCCESS)
        assert payload is not None
        assert payload["user_email"] == test_settings.TEST_EMAIL

    async def test_reset_password_new_credentials_work_on_login(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        new_password = "NewPassword123!"
        await _setup_verified_user(integration_client, get_outbox_event)
        await integration_client.post(f"{test_settings.API}/forgot-password", json={"email": test_settings.TEST_EMAIL, "captcha_token": test_settings.CAPTCHA_TOKEN})
        reset_token = await self._get_reset_token(get_outbox_event)

        await integration_client.post(
            f"{test_settings.API}/password-reset",
            json={"token": reset_token, "new_password": new_password},
        )
        login_resp = await _login(integration_client, password=new_password)
        assert login_resp.status_code == status.HTTP_200_OK

    async def test_reset_password_old_password_no_longer_works(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        new_password = "NewPassword123!"
        await _setup_verified_user(integration_client, get_outbox_event)
        await integration_client.post(f"{test_settings.API}/forgot-password", json={"email": test_settings.TEST_EMAIL, "captcha_token": test_settings.CAPTCHA_TOKEN})
        reset_token = await self._get_reset_token(get_outbox_event)

        await integration_client.post(
            f"{test_settings.API}/password-reset",
            json={"token": reset_token, "new_password": new_password},
        )
        old_login = await _login(integration_client, password=test_settings.TEST_PASSWORD)
        assert old_login.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_reset_password_invalid_token_returns_401(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{test_settings.API}/password-reset",
            json={
                "token": "not-a-valid-reset-token-but-long-enough-to-pass",
                "new_password": "NewPassword123!",
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# GET /api/v1/users/{user_id}
# ===========================================================================


class TestGetUserByIdEndpoint:
    async def test_get_user_by_id_returns_200_and_user_data(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        user_data = await _setup_verified_user(integration_client, get_outbox_event)
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
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ===========================================================================
# GET /api/v1/users
# ===========================================================================


class TestGetAllUsersEndpoint:
    async def test_get_all_users_returns_list_with_one_user(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        await _setup_verified_user(integration_client, get_outbox_event)
        response = await integration_client.get(f"{test_settings.API}/users")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["email"] == test_settings.TEST_EMAIL

    async def test_get_all_users_empty_db_returns_empty_list(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.get(f"{test_settings.API}/users")
        # An empty collection is a successful, empty result — not a 404.
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_get_all_users_pagination_returns_correct_pages(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        # Register and activate two separate users
        for email in ("user1@example.com", "user2@example.com"):
            await _register(integration_client, email=email)
            payload = await get_outbox_event(UserEvents.USER_REGISTERED)
            await integration_client.post(
                f"{test_settings.API}/activate", json={"token": payload["token"]}
            )

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
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ===========================================================================
# PATCH /api/v1/users/{user_id}
# ===========================================================================


class TestUpdateUserEndpoint:
    async def test_update_user_name_returns_200_and_new_name(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        user_data = await _setup_verified_user(integration_client, get_outbox_event)
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
        self, integration_client: AsyncClient, get_outbox_event
    ):
        user_data = await _setup_verified_user(integration_client, get_outbox_event)
        response = await integration_client.patch(
            f"{test_settings.API}/users/{user_data['id']}",
            json={"name": "x"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ===========================================================================
# DELETE /api/v1/users/{user_id}
# ===========================================================================


class TestDeleteUserEndpoint:
    async def test_delete_user_returns_200(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        user_data = await _setup_verified_user(integration_client, get_outbox_event)
        response = await integration_client.delete(f"{test_settings.API}/users/{user_data['id']}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["detail"] == "User deleted successfully"

    async def test_deleted_user_is_no_longer_retrievable(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        user_data = await _setup_verified_user(integration_client, get_outbox_event)
        await integration_client.delete(f"{test_settings.API}/users/{user_data['id']}")
        get_response = await integration_client.get(f"{test_settings.API}/users/{user_data['id']}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_user_creates_deleted_outbox_event(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        user_data = await _setup_verified_user(integration_client, get_outbox_event)
        await integration_client.delete(f"{test_settings.API}/users/{user_data['id']}")
        payload = await get_outbox_event(UserEvents.USER_DELETED)
        assert payload is not None
        assert payload["user_email"] == test_settings.TEST_EMAIL

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

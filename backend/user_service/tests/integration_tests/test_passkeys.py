"""
Admin passkeys end to end: enrolment by link, sign-in with password + passkey,
and the session that results — against the real database and real WebAuthn
verification. The authenticator is a software one with a real P-256 key
(tests/software_authenticator.py); nothing in the server's checks is stubbed.
"""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from webauthn.helpers import bytes_to_base64url

from main import app
from managers import ResourceManager, UserApiResources, settings
from models.user_models import User
from service_layer.passkey_ceremony_store import PasskeyCeremonyStore
from service_layer.session_issuer import SessionIssuer
from shared.contracts.auth import AuthMethod
from shared.managers.cache_manager import CacheManager
from shared.managers.password_manager import PasswordManager
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from tests.conftest import SIGNING_KEYS
from tests.software_authenticator import SoftwareAuthenticator

API = settings.USER_SERVICE_URL_API_VERSION
ADMIN_EMAIL = "owner@example.com"
ADMIN_PASSWORD = "Admin-password-123"
USER_EMAIL = "shopper@example.com"
USER_PASSWORD = "Shopper-password-123"


async def _create_user(manager: TestDatabaseSessionManager, email: str, password: str, role: str) -> UUID:
    async with manager.transaction() as session:
        user = User(
            name=email.split("@")[0],
            email=email,
            hashed_password=PasswordManager(settings).hash_password(password),
            role=role,
            is_verified=True,
            is_active=True,
            token_version=1,
        )
        session.add(user)
        await session.flush()
        return user.id


def _app_cache() -> CacheManager:
    """The (stateful) Redis stand-in the integration client gave the app."""
    resources = getattr(app.state, ResourceManager.STATE_ATTRIBUTE)
    assert isinstance(resources, UserApiResources)
    return resources.cache


def _ceremonies() -> PasskeyCeremonyStore:
    """The store over the same Redis stand-in the app is using."""
    cache = _app_cache()
    return PasskeyCeremonyStore(cache, challenge_ttl_seconds=300, enrolment_ttl_seconds=900)


def _authenticator() -> SoftwareAuthenticator:
    return SoftwareAuthenticator(rp_id=settings.WEBAUTHN_RP_ID, origin=settings.WEBAUTHN_ORIGINS[0])


@pytest.fixture
async def admin_id(integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager) -> UUID:
    return await _create_user(test_database_session_manager, ADMIN_EMAIL, ADMIN_PASSWORD, settings.SECRET_ROLE)


@pytest.fixture
async def enrolled(integration_client: AsyncClient, admin_id: UUID) -> AsyncGenerator[SoftwareAuthenticator, Any]:
    """An admin with one passkey, registered the way the owner's link does it."""
    authenticator = _authenticator()
    token = await _ceremonies().issue_enrolment_token(admin_id)
    started = await integration_client.post(f"{API}/passkeys/enrolment/options", json={"token": token})
    assert started.status_code == 200, started.text
    body = started.json()
    finished = await integration_client.post(
        f"{API}/passkeys/enrolment/verify",
        json={
            "token": token,
            "challenge_id": body["challenge_id"],
            "credential": authenticator.create(body["options"]),
            "name": "Test laptop",
        },
    )
    assert finished.status_code == 201, finished.text
    yield authenticator


async def _start_sign_in(client: AsyncClient, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> dict[str, Any]:
    response = await client.post(f"{API}/login/passkey/options", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------- enrolment ---------------------------------


async def test_enrolment_registers_the_passkey_and_spends_the_link(
    integration_client: AsyncClient, admin_id: UUID
) -> None:
    authenticator = _authenticator()
    token = await _ceremonies().issue_enrolment_token(admin_id)
    started = (await integration_client.post(f"{API}/passkeys/enrolment/options", json={"token": token})).json()

    # The options name the admin and demand user verification.
    assert started["options"]["rp"]["id"] == settings.WEBAUTHN_RP_ID
    assert started["options"]["user"]["name"] == ADMIN_EMAIL
    assert started["options"]["authenticatorSelection"]["userVerification"] == "required"

    finished = await integration_client.post(
        f"{API}/passkeys/enrolment/verify",
        json={
            "token": token,
            "challenge_id": started["challenge_id"],
            "credential": authenticator.create(started["options"]),
            "name": "Test laptop",
        },
    )
    assert finished.status_code == 201, finished.text
    assert finished.json()["name"] == "Test laptop"

    # Single use: the same link cannot register a second passkey.
    again = await integration_client.post(f"{API}/passkeys/enrolment/options", json={"token": token})
    assert again.status_code == 401


async def test_enrolment_without_user_verification_is_refused_and_keeps_the_link(
    integration_client: AsyncClient, admin_id: UUID
) -> None:
    token = await _ceremonies().issue_enrolment_token(admin_id)
    started = (await integration_client.post(f"{API}/passkeys/enrolment/options", json={"token": token})).json()
    refused = await integration_client.post(
        f"{API}/passkeys/enrolment/verify",
        json={
            "token": token,
            "challenge_id": started["challenge_id"],
            "credential": _authenticator().create(started["options"], user_verified=False),
            "name": "No PIN",
        },
    )
    assert refused.status_code == 400
    # A failed attempt does not burn the owner's link.
    retry = await integration_client.post(f"{API}/passkeys/enrolment/options", json={"token": token})
    assert retry.status_code == 200


async def test_enrolment_from_another_origin_is_refused(integration_client: AsyncClient, admin_id: UUID) -> None:
    token = await _ceremonies().issue_enrolment_token(admin_id)
    started = (await integration_client.post(f"{API}/passkeys/enrolment/options", json={"token": token})).json()
    refused = await integration_client.post(
        f"{API}/passkeys/enrolment/verify",
        json={
            "token": token,
            "challenge_id": started["challenge_id"],
            "credential": _authenticator().create(started["options"], origin="https://phishing.example"),
            "name": "Phished",
        },
    )
    assert refused.status_code == 400


async def test_enrolment_link_for_a_non_admin_is_refused(
    integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    user_id = await _create_user(test_database_session_manager, USER_EMAIL, USER_PASSWORD, "user")
    token = await _ceremonies().issue_enrolment_token(user_id)
    response = await integration_client.post(f"{API}/passkeys/enrolment/options", json={"token": token})
    assert response.status_code == 403


async def test_enrolment_answer_needs_the_link_it_was_started_with(
    integration_client: AsyncClient, admin_id: UUID
) -> None:
    ceremonies = _ceremonies()
    token = await ceremonies.issue_enrolment_token(admin_id)
    other_token = await ceremonies.issue_enrolment_token(admin_id)
    started = (await integration_client.post(f"{API}/passkeys/enrolment/options", json={"token": token})).json()
    refused = await integration_client.post(
        f"{API}/passkeys/enrolment/verify",
        json={
            "token": other_token,
            "challenge_id": started["challenge_id"],
            "credential": _authenticator().create(started["options"]),
            "name": "Swapped link",
        },
    )
    assert refused.status_code == 400


# -------------------------------- sign-in ----------------------------------


async def test_admin_password_login_is_refused(integration_client: AsyncClient, enrolled: SoftwareAuthenticator) -> None:
    response = await integration_client.post(
        f"{API}/login", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 403
    assert "passkey" in response.json()["detail"]


async def test_passkey_sign_in_issues_a_session_marked_with_both_factors(
    integration_client: AsyncClient, enrolled: SoftwareAuthenticator
) -> None:
    started = await _start_sign_in(integration_client)
    assert started["options"]["userVerification"] == "required"
    # Only the admin's own passkeys are offered.
    assert [c["id"] for c in started["options"]["allowCredentials"]] == [bytes_to_base64url(enrolled.credential_id)]

    signed_in = await integration_client.post(
        f"{API}/login/passkey/verify",
        json={"challenge_id": started["challenge_id"], "credential": enrolled.get(started["options"])},
    )
    assert signed_in.status_code == 200, signed_in.text
    body = signed_in.json()
    assert body["user_email"] == ADMIN_EMAIL and body["user_role"] == settings.SECRET_ROLE

    claims = SIGNING_KEYS.user_token_verifier().decode(body["access_token"])
    assert set(claims.amr) == {AuthMethod.PASSWORD, AuthMethod.PASSKEY}
    assert claims.signed_in_with_passkey()

    # A refresh keeps the session's sign-in methods.
    refreshed = await integration_client.post(f"{API}/refresh", json={"refresh_token": body["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    refreshed_claims = SIGNING_KEYS.user_token_verifier().decode(refreshed.json()["access_token"])
    assert refreshed_claims.signed_in_with_passkey()


async def test_a_signed_answer_cannot_be_replayed(integration_client: AsyncClient, enrolled: SoftwareAuthenticator) -> None:
    started = await _start_sign_in(integration_client)
    answer = enrolled.get(started["options"])
    first = await integration_client.post(
        f"{API}/login/passkey/verify", json={"challenge_id": started["challenge_id"], "credential": answer}
    )
    assert first.status_code == 200
    replay = await integration_client.post(
        f"{API}/login/passkey/verify", json={"challenge_id": started["challenge_id"], "credential": answer}
    )
    assert replay.status_code == 401


async def test_sign_in_without_user_verification_is_refused(
    integration_client: AsyncClient, enrolled: SoftwareAuthenticator
) -> None:
    started = await _start_sign_in(integration_client)
    response = await integration_client.post(
        f"{API}/login/passkey/verify",
        json={"challenge_id": started["challenge_id"], "credential": enrolled.get(started["options"], user_verified=False)},
    )
    assert response.status_code == 401


async def test_sign_in_from_another_origin_is_refused(
    integration_client: AsyncClient, enrolled: SoftwareAuthenticator
) -> None:
    started = await _start_sign_in(integration_client)
    response = await integration_client.post(
        f"{API}/login/passkey/verify",
        json={
            "challenge_id": started["challenge_id"],
            "credential": enrolled.get(started["options"], origin="https://phishing.example"),
        },
    )
    assert response.status_code == 401


async def test_a_counter_that_goes_backwards_is_refused(
    integration_client: AsyncClient, enrolled: SoftwareAuthenticator
) -> None:
    # One good sign-in raises the stored counter to 1 ...
    started = await _start_sign_in(integration_client)
    ok = await integration_client.post(
        f"{API}/login/passkey/verify",
        json={"challenge_id": started["challenge_id"], "credential": enrolled.get(started["options"])},
    )
    assert ok.status_code == 200
    # ... so an answer that does not advance it is what a cloned key looks like.
    started = await _start_sign_in(integration_client)
    cloned = await integration_client.post(
        f"{API}/login/passkey/verify",
        json={"challenge_id": started["challenge_id"], "credential": enrolled.get(started["options"], advance_counter=False)},
    )
    assert cloned.status_code == 401


async def test_another_key_cannot_answer_for_the_registered_one(
    integration_client: AsyncClient, enrolled: SoftwareAuthenticator
) -> None:
    started = await _start_sign_in(integration_client)
    impostor = SoftwareAuthenticator(
        rp_id=settings.WEBAUTHN_RP_ID, origin=settings.WEBAUTHN_ORIGINS[0], credential_id=enrolled.credential_id
    )
    response = await integration_client.post(
        f"{API}/login/passkey/verify",
        json={"challenge_id": started["challenge_id"], "credential": impostor.get(started["options"])},
    )
    assert response.status_code == 401


async def test_wrong_password_never_reaches_the_passkey_step(
    integration_client: AsyncClient, enrolled: SoftwareAuthenticator
) -> None:
    response = await integration_client.post(
        f"{API}/login/passkey/options", json={"email": ADMIN_EMAIL, "password": "not-the-password"}
    )
    assert response.status_code == 401


async def test_admin_without_a_passkey_is_told_to_ask_for_a_link(
    integration_client: AsyncClient, admin_id: UUID
) -> None:
    response = await integration_client.post(
        f"{API}/login/passkey/options", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 403
    assert "enrolment link" in response.json()["detail"]


async def test_passkey_sign_in_is_for_admins_only(
    integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    await _create_user(test_database_session_manager, USER_EMAIL, USER_PASSWORD, "user")
    response = await integration_client.post(
        f"{API}/login/passkey/options", json={"email": USER_EMAIL, "password": USER_PASSWORD}
    )
    assert response.status_code == 403


async def test_admin_refresh_without_a_passkey_mints_nothing(
    integration_client: AsyncClient, admin_id: UUID, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    """A session from before passkeys (or a user promoted while signed in)."""
    async with test_database_session_manager.transaction() as session:
        admin = await session.get(User, admin_id)
        assert admin is not None
        issuer = SessionIssuer(SIGNING_KEYS.token_manager(settings), _app_cache(), settings)
        password_only = await issuer.issue(admin, [AuthMethod.PASSWORD])

    response = await integration_client.post(f"{API}/refresh", json={"refresh_token": password_only.refresh_token})
    assert response.status_code == 401
    assert "passkey" in response.json()["detail"]


async def test_shopper_password_login_still_works(
    integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    await _create_user(test_database_session_manager, USER_EMAIL, USER_PASSWORD, "user")
    response = await integration_client.post(f"{API}/login", data={"username": USER_EMAIL, "password": USER_PASSWORD})
    assert response.status_code == 200, response.text
    claims = SIGNING_KEYS.user_token_verifier().decode(response.json()["access_token"])
    assert claims.amr == [AuthMethod.PASSWORD]

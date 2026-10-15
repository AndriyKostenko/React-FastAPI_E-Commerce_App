"""
The address book (/users/me/addresses) and the signed-in password change
(/users/me/password), against the real test database and the real services.
Only Redis and RabbitMQ are stand-ins, as in the rest of this suite.
"""
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import status
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from contracts.event_enums import UserEvents
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.address_models import UserAddress
from service_layer.address_service import AddressService
from settings import get_test_settings
from tests.conftest import as_gateway
from tests.integration_tests.test_user_routes import _login, _setup_authenticated_user

test_settings = get_test_settings()
API = test_settings.API
ADDRESSES = f"{API}/users/me/addresses"

OutboxReader = Callable[[str], Awaitable[dict[str, Any] | None]]

OTHER_EMAIL = "other@example.com"
OTHER_PASSWORD = "Other-password-123"


def _address(**overrides: str | bool | None) -> dict[str, str | bool | None]:
    body: dict[str, str | bool | None] = {
        "label": "Home",
        "name": "Test User",
        "phone": "+1 416 555 0100",
        "street": "100 King St W",
        "city": "Toronto",
        "province": "ON",
        "postal_code": "M5X 1A9",
        "is_default": False,
    }
    body.update(overrides)
    return body


class _Caller:
    """One signed-in user, making requests the way the gateway forwards them."""

    def __init__(self, client: AsyncClient, access_token: str) -> None:
        self._client = client
        self._token = access_token

    def _headers(self, method: str, path: str) -> dict[str, str]:
        return as_gateway(self._token, method, path)

    async def get(self, path: str) -> Response:
        return await self._client.get(path, headers=self._headers("GET", path))

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Response:
        return await self._client.post(path, json=json, headers=self._headers("POST", path))

    async def put(self, path: str, json: dict[str, Any]) -> Response:
        return await self._client.put(path, json=json, headers=self._headers("PUT", path))

    async def delete(self, path: str) -> Response:
        return await self._client.delete(path, headers=self._headers("DELETE", path))


async def _signed_in(
    client: AsyncClient,
    get_outbox_event: OutboxReader,
    *,
    email: str = test_settings.TEST_EMAIL,
    password: str = test_settings.TEST_PASSWORD,
) -> _Caller:
    login = await _setup_authenticated_user(client, get_outbox_event, email=email, password=password)
    return _Caller(client, str(login["access_token"]))


async def _create(caller: _Caller, **overrides: str | bool | None) -> dict[str, Any]:
    response = await caller.post(ADDRESSES, json=_address(**overrides))
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _defaults(caller: _Caller) -> list[str]:
    response = await caller.get(ADDRESSES)
    return [row["id"] for row in response.json() if row["is_default"]]


# ===========================================================================
# Saving and listing
# ===========================================================================


class TestCreateAndList:
    async def test_empty_book_lists_nothing(self, integration_client: AsyncClient, get_outbox_event):
        caller = await _signed_in(integration_client, get_outbox_event)
        response = await caller.get(ADDRESSES)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_first_address_becomes_the_default_even_when_not_asked(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        caller = await _signed_in(integration_client, get_outbox_event)
        created = await _create(caller, is_default=False)
        assert created["is_default"] is True

    async def test_address_is_normalised_like_an_order_address(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        caller = await _signed_in(integration_client, get_outbox_event)
        created = await _create(caller, province="ontario", postal_code="m5x1a9")
        assert created["province"] == "ON"
        assert created["postal_code"] == "M5X 1A9"
        assert created["country"] == "Canada"
        assert created["country_code"] == "CA"

    async def test_non_canadian_address_is_refused(self, integration_client: AsyncClient, get_outbox_event):
        caller = await _signed_in(integration_client, get_outbox_event)
        response = await caller.post(ADDRESSES, json={**_address(), "country_code": "US"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert (await caller.get(ADDRESSES)).json() == []

    async def test_malformed_postal_code_is_refused(self, integration_client: AsyncClient, get_outbox_event):
        caller = await _signed_in(integration_client, get_outbox_event)
        response = await caller.post(ADDRESSES, json=_address(postal_code="12345"))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_new_default_takes_over_from_the_old_one(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        caller = await _signed_in(integration_client, get_outbox_event)
        first = await _create(caller, label="Home")
        second = await _create(caller, label="Work", is_default=True)

        assert await _defaults(caller) == [second["id"]]
        listed = (await caller.get(ADDRESSES)).json()
        # The default is listed first.
        assert [row["id"] for row in listed] == [second["id"], first["id"]]

    async def test_book_is_capped(self, integration_client: AsyncClient, get_outbox_event):
        caller = await _signed_in(integration_client, get_outbox_event)
        for index in range(AddressService.MAX_ADDRESSES_PER_USER):
            await _create(caller, label=f"Address {index}")
        response = await caller.post(ADDRESSES, json=_address(label="One too many"))
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_without_a_session_is_refused(self, integration_client: AsyncClient):
        response = await integration_client.get(ADDRESSES)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# Replacing, moving the default, deleting
# ===========================================================================


class TestChange:
    async def test_replace_updates_the_fields(self, integration_client: AsyncClient, get_outbox_event):
        caller = await _signed_in(integration_client, get_outbox_event)
        created = await _create(caller)
        response = await caller.put(
            f"{ADDRESSES}/{created['id']}",
            json=_address(label="Cottage", city="Vancouver", province="BC", postal_code="V6B 1A1"),
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert (body["label"], body["city"], body["province"]) == ("Cottage", "Vancouver", "BC")

    async def test_saving_the_default_as_not_default_keeps_it_the_default(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        caller = await _signed_in(integration_client, get_outbox_event)
        only = await _create(caller)
        response = await caller.put(f"{ADDRESSES}/{only['id']}", json=_address(is_default=False))
        assert response.json()["is_default"] is True

    async def test_make_default_moves_it(self, integration_client: AsyncClient, get_outbox_event):
        caller = await _signed_in(integration_client, get_outbox_event)
        await _create(caller, label="Home")
        work = await _create(caller, label="Work")

        response = await caller.post(f"{ADDRESSES}/{work['id']}/default")
        assert response.status_code == status.HTTP_200_OK
        assert await _defaults(caller) == [work["id"]]

    async def test_deleting_the_default_promotes_the_oldest_remaining(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        caller = await _signed_in(integration_client, get_outbox_event)
        home = await _create(caller, label="Home")
        work = await _create(caller, label="Work")
        cottage = await _create(caller, label="Cottage", is_default=True)

        response = await caller.delete(f"{ADDRESSES}/{cottage['id']}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert await _defaults(caller) == [home["id"]]
        remaining = {row["id"] for row in (await caller.get(ADDRESSES)).json()}
        assert remaining == {home["id"], work["id"]}


# ===========================================================================
# One user's book is invisible to another
# ===========================================================================


class TestIsolation:
    async def test_another_users_address_reads_as_missing(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        owner = await _signed_in(integration_client, get_outbox_event)
        address = await _create(owner)
        other = await _signed_in(integration_client, get_outbox_event, email=OTHER_EMAIL, password=OTHER_PASSWORD)

        assert (await other.get(ADDRESSES)).json() == []
        target = f"{ADDRESSES}/{address['id']}"
        assert (await other.put(target, json=_address(label="Mine now"))).status_code == status.HTTP_404_NOT_FOUND
        assert (await other.post(f"{target}/default")).status_code == status.HTTP_404_NOT_FOUND
        assert (await other.delete(target)).status_code == status.HTTP_404_NOT_FOUND

        # Untouched for its owner.
        listed = (await owner.get(ADDRESSES)).json()
        assert [(row["id"], row["label"]) for row in listed] == [(address["id"], "Home")]


class TestAccountDeletion:
    async def test_deleting_the_account_deletes_its_addresses(
        self,
        integration_client: AsyncClient,
        get_outbox_event,
        test_database_session_manager: TestDatabaseSessionManager,
    ):
        caller = await _signed_in(integration_client, get_outbox_event)
        created = await _create(caller)
        await _create(caller, label="Work")

        me = (await caller.get(f"{API}/me")).json()
        response = await caller.delete(f"{API}/users/{me['id']}")
        assert response.status_code == status.HTTP_200_OK

        async with test_database_session_manager.transaction() as session:
            remaining = await session.execute(select(func.count()).select_from(UserAddress))
            assert remaining.scalar_one() == 0
            assert await session.get(UserAddress, created["id"]) is None


# ===========================================================================
# POST /users/me/password
# ===========================================================================


PASSWORD_PATH = f"{API}/users/me/password"
NEW_PASSWORD = "Brand-new-password-456"


class TestChangePassword:
    async def test_change_replaces_the_password_and_announces_it(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        caller = await _signed_in(integration_client, get_outbox_event)
        response = await caller.post(
            PASSWORD_PATH,
            json={"current_password": test_settings.TEST_PASSWORD, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == status.HTTP_200_OK, response.text

        old = await _login(integration_client, password=test_settings.TEST_PASSWORD)
        assert old.status_code == status.HTTP_401_UNAUTHORIZED
        new = await _login(integration_client, password=NEW_PASSWORD)
        assert new.status_code == status.HTTP_200_OK

        event = await get_outbox_event(UserEvents.USER_PASSWORD_RESET_SUCCESS)
        assert event is not None
        assert event["user_email"] == test_settings.TEST_EMAIL

    async def test_change_ends_existing_sessions(self, integration_client: AsyncClient, get_outbox_event):
        login = await _setup_authenticated_user(integration_client, get_outbox_event)
        caller = _Caller(integration_client, str(login["access_token"]))
        await caller.post(
            PASSWORD_PATH,
            json={"current_password": test_settings.TEST_PASSWORD, "new_password": NEW_PASSWORD},
        )
        # The refresh token issued before the change no longer mints access tokens.
        refresh = await integration_client.post(
            f"{API}/refresh", json={"refresh_token": login["refresh_token"]}
        )
        assert refresh.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_wrong_current_password_is_refused_without_signing_out(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        caller = await _signed_in(integration_client, get_outbox_event)
        response = await caller.post(
            PASSWORD_PATH, json={"current_password": "not-my-password", "new_password": NEW_PASSWORD}
        )
        # 400, not 401: a 401 would read as an expired session to the storefront.
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (await _login(integration_client)).status_code == status.HTTP_200_OK

    async def test_same_password_is_refused(self, integration_client: AsyncClient, get_outbox_event):
        caller = await _signed_in(integration_client, get_outbox_event)
        response = await caller.post(
            PASSWORD_PATH,
            json={"current_password": test_settings.TEST_PASSWORD, "new_password": test_settings.TEST_PASSWORD},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_short_new_password_is_refused(self, integration_client: AsyncClient, get_outbox_event):
        caller = await _signed_in(integration_client, get_outbox_event)
        response = await caller.post(
            PASSWORD_PATH, json={"current_password": test_settings.TEST_PASSWORD, "new_password": "short"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

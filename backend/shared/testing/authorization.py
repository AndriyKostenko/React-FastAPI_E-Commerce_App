"""Helpers for the per-service route-authorisation tests (bug list 4)."""

from dataclasses import dataclass, field
from uuid import UUID

import httpx

from shared.settings import get_settings
from shared.testing.signing_keys import ANONYMOUS, EphemeralSigningKeys


@dataclass(frozen=True, slots=True)
class RouteCase:
    method: str
    path: str
    json: dict[str, object] | None = field(default=None)

    def __str__(self) -> str:
        return f"{self.method} {self.path}"


class Callers:
    """Named callers, each signed with the test app's trusted gateway keys."""

    def __init__(self, keys: EphemeralSigningKeys) -> None:
        self._keys = keys

    def user(self, user_id: UUID) -> httpx.Auth:
        return self._keys.caller_auth(user_id=user_id, role="user")

    def admin(self, user_id: UUID = UUID("00000000-0000-4000-8000-00000000ad02")) -> httpx.Auth:
        return self._keys.caller_auth(user_id=user_id, role=get_settings().SECRET_ROLE)

    @property
    def anonymous(self) -> httpx.Auth:
        return ANONYMOUS


async def call(client: httpx.AsyncClient, case: RouteCase, auth: httpx.Auth) -> httpx.Response:
    return await client.request(case.method, case.path, json=case.json, auth=auth)


async def assert_denied(client: httpx.AsyncClient, case: RouteCase, auth: httpx.Auth, status: int) -> None:
    response = await call(client, case, auth)
    assert response.status_code == status, f"{case}: expected {status}, got {response.status_code} {response.text}"


async def assert_allowed(client: httpx.AsyncClient, case: RouteCase, auth: httpx.Auth) -> None:
    """Authorisation let it through — whatever the handler then made of it."""
    response = await call(client, case, auth)
    assert response.status_code not in (401, 403), f"{case}: refused {response.status_code} {response.text}"

"""
The gateway's caller assertion, end to end through the real middleware and
real Ed25519 keys: what a service believes about its caller, and what it
refuses to believe.
"""

from datetime import timedelta
from logging import getLogger
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from shared.auth.caller_assertion import (
    CALLER_ASSERTION_HEADER,
    CallerAssertionSigner,
    RequestTarget,
)
from shared.contracts.auth import TokenClaims
from shared.middleware.caller_assertion_middleware import CallerAssertionMiddleware
from shared.testing.signing_keys import (
    TEST_ASSERTION_AUDIENCE,
    TEST_ASSERTION_ISSUER,
    EphemeralSigningKeys,
)
from shared.utils.authenticated_caller import AuthenticatedCaller


KEYS = EphemeralSigningKeys()
USER_ID = uuid4()
PATH = "/api/v1/orders/123"


def _service(keys: EphemeralSigningKeys | None = KEYS) -> FastAPI:
    app = FastAPI()
    app.add_middleware(CallerAssertionMiddleware, logger=getLogger("test.caller-assertion"))
    if keys is not None:
        keys.install_verifier(app)

    @app.api_route("/api/v1/orders/{order_id}", methods=["GET", "DELETE"])
    async def whoami(request: Request, order_id: str) -> dict[str, str | None]:
        caller = AuthenticatedCaller.from_request(request)
        return {"user_id": str(caller.user_id) if caller.user_id else None, "role": caller.role}

    return app


async def _call(app: FastAPI, method: str = "GET", path: str = PATH, headers: dict[str, str] | None = None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://service") as client:
        return await client.request(method, path, headers=headers or {})


async def test_request_without_assertion_is_anonymous() -> None:
    response = await _call(_service())
    assert response.status_code == 200
    assert response.json() == {"user_id": None, "role": None}


async def test_valid_assertion_names_the_caller() -> None:
    headers = KEYS.caller_headers("GET", PATH, user_id=USER_ID, role="admin")
    response = await _call(_service(), headers=headers)
    assert response.json() == {"user_id": str(USER_ID), "role": "admin"}


async def test_anonymous_assertion_from_the_gateway_is_anonymous() -> None:
    assertion = KEYS.assertion_signer().sign(None, RequestTarget("GET", PATH))
    response = await _call(_service(), headers={CALLER_ASSERTION_HEADER: assertion})
    assert response.json() == {"user_id": None, "role": None}


async def test_trailing_slash_does_not_break_the_binding() -> None:
    headers = KEYS.caller_headers("GET", PATH + "/", user_id=USER_ID)
    assert (await _call(_service(), headers=headers)).status_code == 200


@pytest.mark.parametrize(
    ("scenario", "headers"),
    [
        # Minted by someone without the gateway's private key: the attack the
        # old plain X-Authenticated-User-Id header could not stop.
        ("forged-key", EphemeralSigningKeys().caller_headers("GET", PATH, user_id=USER_ID, role="admin")),
        # Captured on the network, replayed against a different resource...
        ("other-path", KEYS.caller_headers("GET", "/api/v1/orders/999", user_id=USER_ID)),
        # ...or a different verb on the same one.
        ("other-method", KEYS.caller_headers("DELETE", PATH, user_id=USER_ID)),
        ("garbage", {CALLER_ASSERTION_HEADER: "not-a-jwt"}),
    ],
)
async def test_assertion_that_does_not_verify_is_rejected(scenario: str, headers: dict[str, str]) -> None:
    response = await _call(_service(), headers=headers)
    assert response.status_code == 401, scenario
    assert response.json()["error"] == "invalid_caller_assertion"


async def test_expired_assertion_is_rejected() -> None:
    expired_signer = CallerAssertionSigner(
        KEYS.gateway_assertion_private_key,
        TEST_ASSERTION_ISSUER,
        TEST_ASSERTION_AUDIENCE,
        ttl=timedelta(seconds=-30),  # beyond the 5s clock-skew allowance
    )
    claims = TokenClaims(email="caller@example.com", id=USER_ID, role="user")
    assertion = expired_signer.sign(claims, RequestTarget("GET", PATH))
    response = await _call(_service(), headers={CALLER_ASSERTION_HEADER: assertion})
    assert response.status_code == 401


async def test_plain_identity_headers_are_ignored() -> None:
    # The retired headers must grant nothing, even with no assertion present.
    response = await _call(
        _service(),
        headers={"X-Authenticated-User-Id": str(USER_ID), "X-Authenticated-User-Role": "admin"},
    )
    assert response.json() == {"user_id": None, "role": None}


async def test_service_without_a_verifier_fails_closed() -> None:
    headers = KEYS.caller_headers("GET", PATH, user_id=USER_ID)
    response = await _call(_service(keys=None), headers=headers)
    assert response.status_code == 401

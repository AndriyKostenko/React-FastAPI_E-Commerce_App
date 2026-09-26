"""
Service-to-service identity end to end: order-service's signing auth on one
side, require_service on the other, real Ed25519 keys in between.
"""

from types import SimpleNamespace
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from shared.auth.caller_assertion import RequestTarget
from shared.auth.service_assertion import SERVICE_ASSERTION_HEADER, ServiceCallerGuard
from shared.testing.signing_keys import EphemeralSigningKeys


KEYS = EphemeralSigningKeys()


def _service(keys: EphemeralSigningKeys = KEYS, trusted: bool = True) -> FastAPI:
    settings = SimpleNamespace(ORDER_SERVICE_ASSERTION_PUBLIC_KEY=None)
    if trusted:
        keys.trust_order_service(settings)
    guard = ServiceCallerGuard("order-service", settings_provider=lambda: settings)  # type: ignore[arg-type,return-value]
    app = FastAPI()

    @app.post("/products/order-quote")
    async def quote(caller: Annotated[str, Depends(guard)]) -> dict[str, str]:
        return {"caller": caller}

    return app


async def _post(app: FastAPI, path: str = "/products/order-quote", **kwargs) -> int:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://product") as client:
        return (await client.post(path, **kwargs)).status_code


async def test_order_service_is_admitted() -> None:
    assert await _post(_service(), auth=KEYS.order_service_auth()) == 200


async def test_an_unsigned_internal_call_is_refused() -> None:
    assert await _post(_service()) == 401


async def test_another_key_cannot_pose_as_order_service() -> None:
    assert await _post(_service(), auth=EphemeralSigningKeys().order_service_auth()) == 401


async def test_a_users_gateway_assertion_is_not_a_service_identity() -> None:
    # Even an admin, correctly signed by the gateway, is not order-service.
    admin = KEYS.caller_auth(user_id=uuid4(), role="admin")
    assert await _post(_service(), auth=admin) == 401


async def test_an_assertion_for_another_route_is_refused() -> None:
    app = FastAPI()
    settings = SimpleNamespace(ORDER_SERVICE_ASSERTION_PUBLIC_KEY=None)
    KEYS.trust_order_service(settings)
    guard = ServiceCallerGuard("order-service", settings_provider=lambda: settings)  # type: ignore[arg-type,return-value]

    @app.post("/artwork/download-link")
    async def link(caller: Annotated[str, Depends(guard)]) -> dict[str, str]:
        return {"caller": caller}

    # Signed for /products/order-quote, replayed against /artwork/download-link.
    signer_auth = KEYS.order_service_auth()
    signer = signer_auth._signer_factory()
    stolen = signer.sign(None, RequestTarget("POST", "/products/order-quote"))
    assert await _post(app, "/artwork/download-link", headers={SERVICE_ASSERTION_HEADER: stolen}) == 401


async def test_without_the_public_key_the_route_fails_closed() -> None:
    assert await _post(_service(trusted=False), auth=KEYS.order_service_auth()) == 401

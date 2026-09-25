"""Throwaway Ed25519 keys so tests sign and verify for real without any .env secret."""

from collections.abc import Generator
from datetime import timedelta
from uuid import UUID

import httpx

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI

from shared.auth.caller_assertion import (
    CALLER_ASSERTION_HEADER,
    CallerAssertionSigner,
    CallerAssertionVerifier,
    RequestTarget,
)
from shared.auth.user_tokens import UserTokenIssuer, UserTokenVerifier
from shared.contracts.auth import TokenClaims
from shared.middleware.caller_assertion_middleware import VERIFIER_STATE_KEY
from shared.managers.token_manager import TokenManager
from shared.settings import Settings, TestSettings


TEST_TOKEN_ISSUER = "user-service"
TEST_TOKEN_AUDIENCE = "ecommerce-api"
TEST_ASSERTION_ISSUER = "api-gateway"
TEST_ASSERTION_AUDIENCE = "internal-services"


class GatewayCallerAuth(httpx.Auth):
    """
    Signs each test request the way the gateway signs a proxied one: an
    assertion for this caller, bound to that request's own method and path.
    """

    def __init__(self, signer: CallerAssertionSigner, caller: TokenClaims) -> None:
        self._signer = signer
        self._caller = caller

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        target = RequestTarget(method=request.method, path=request.url.path)
        request.headers[CALLER_ASSERTION_HEADER] = self._signer.sign(self._caller, target)
        yield request


class EphemeralSigningKeys:
    """Fresh user-token and gateway-assertion keypairs per instance — real crypto, no mocks."""

    def __init__(self) -> None:
        self.user_token_private_key = Ed25519PrivateKey.generate()
        self.gateway_assertion_private_key = Ed25519PrivateKey.generate()

    def user_token_issuer(self) -> UserTokenIssuer:
        return UserTokenIssuer(self.user_token_private_key, TEST_TOKEN_ISSUER, TEST_TOKEN_AUDIENCE)

    def user_token_verifier(self) -> UserTokenVerifier:
        return UserTokenVerifier(
            self.user_token_private_key.public_key(), TEST_TOKEN_ISSUER, TEST_TOKEN_AUDIENCE
        )

    def token_manager(self, settings: Settings | TestSettings) -> TokenManager:
        # TokenManager reads only REFRESH_TOKEN_TIME_DELTA_DAYS from settings,
        # which TestSettings provides too.
        return TokenManager(
            settings=settings,  # type: ignore[arg-type]
            issuer=self.user_token_issuer(),
            verifier=self.user_token_verifier(),
        )

    def assertion_signer(self) -> CallerAssertionSigner:
        return CallerAssertionSigner(
            self.gateway_assertion_private_key,
            TEST_ASSERTION_ISSUER,
            TEST_ASSERTION_AUDIENCE,
            ttl=timedelta(seconds=60),
        )

    def assertion_verifier(self) -> CallerAssertionVerifier:
        return CallerAssertionVerifier(
            self.gateway_assertion_private_key.public_key(),
            TEST_ASSERTION_ISSUER,
            TEST_ASSERTION_AUDIENCE,
        )

    def install_verifier(self, app: FastAPI) -> None:
        """Make a built service app trust assertions signed by these keys."""
        setattr(app.state, VERIFIER_STATE_KEY, self.assertion_verifier())

    def caller_headers(
        self,
        method: str,
        path: str,
        *,
        user_id: UUID,
        role: str = "user",
        email: str = "caller@example.com",
    ) -> dict[str, str]:
        """Headers the gateway would send for ``user_id`` calling ``method path``."""
        claims = TokenClaims(email=email, id=user_id, role=role)
        assertion = self.assertion_signer().sign(claims, RequestTarget(method=method, path=path))
        return {CALLER_ASSERTION_HEADER: assertion}

    def caller_auth(
        self, *, user_id: UUID, role: str = "user", email: str = "caller@example.com"
    ) -> GatewayCallerAuth:
        """``auth=`` for an httpx test client: every request arrives as this caller."""
        return GatewayCallerAuth(
            self.assertion_signer(), TokenClaims(email=email, id=user_id, role=role)
        )

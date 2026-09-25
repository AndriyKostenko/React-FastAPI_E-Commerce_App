"""Throwaway Ed25519 keys so tests sign and verify for real without any .env secret."""

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from shared.auth.user_tokens import UserTokenIssuer, UserTokenVerifier
from shared.managers.token_manager import TokenManager
from shared.settings import Settings, TestSettings


TEST_TOKEN_ISSUER = "user-service"
TEST_TOKEN_AUDIENCE = "ecommerce-api"


class EphemeralSigningKeys:
    """A fresh user-token keypair per instance — real crypto, no mocks."""

    def __init__(self) -> None:
        self.user_token_private_key = Ed25519PrivateKey.generate()

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

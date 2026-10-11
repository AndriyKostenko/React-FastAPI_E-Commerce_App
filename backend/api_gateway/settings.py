"""The API gateway's settings: only the fields it, and the infrastructure it
uses, read. Names match the keys in the backend config file and in this
service's Vault path, so every value is still set where it was before.
"""

from functools import lru_cache
from pathlib import Path
from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from shared.vault import VaultSettingsSource

# Resolve the single .env that lives one level above this file (backend/.env).
# It is the one source of configuration; real environment variables (compose's
# env_file:) still take precedence over it.
_ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",  # ignore vars in .env that aren't declared on this model
        # A validation error would otherwise print part of the input, which now
        # includes this service's secrets from Vault.
        hide_input_in_errors=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Secrets come from Vault (this service's own path only); the file holds
        # the rest of the configuration. Real environment variables still win.
        return (init_settings, env_settings, VaultSettingsSource(settings_cls), dotenv_settings, file_secret_settings)

    # Application configuration
    APP_HOST: str

    API_GATEWAY_SERVICE_APP_PORT: int

    DEBUG_MODE: bool
    SECURE_COOKIES: bool  # Set True in production (requires HTTPS)

    # Hosts this service answers to
    ALLOWED_HOSTS: list[str]
    # Hostnames a service answers to from inside the mesh. Service-to-service
    # calls address each other by their container DNS name, so that name is a
    # legitimate Host value even though it is never publicly routable. Keeping
    # it separate from ALLOWED_HOSTS lets the public list stay exactly as
    # narrow as the deployment requires, without an IP-based bypass that would
    # accept any Host header at all from inside the network.
    INTERNAL_ALLOWED_HOSTS: list[str] = Field(
        default_factory=lambda: [
            "api-gateway",
            "user-service",
            "product-service",
            "order-service",
            "payment-service",
            "cart-service",
            "shipping-service",
            "wishlist-service",
            "supplier-service",
            "notification-service",
            "admin-js-service",
        ]
    )
    # Only these reverse-proxy networks may supply X-Forwarded-For.  An empty
    # list means the peer address is used directly.  Traefik and the gateway
    # always reach a service over the private Docker network, so the RFC-1918
    # ranges are the working default; narrow them to the compose subnet if the
    # deployment ever places real clients on a private network.
    TRUSTED_PROXY_NETWORKS: list[str] = Field(
        default_factory=lambda: [
            "127.0.0.0/8",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
        ]
    )

    # Service URLs
    USER_SERVICE_URL: str
    PRODUCT_SERVICE_URL: str
    NOTIFICATION_SERVICE_URL: str
    ORDER_SERVICE_URL: str
    PAYMENT_SERVICE_URL: str
    CART_SERVICE_URL: str
    SHIPPING_SERVICE_URL: str
    WISHLIST_SERVICE_URL: str
    SUPPLIER_SERVICE_URL: str

    API_GATEWAY_SERVICE_URL_API_VERSION: str
    USER_SERVICE_URL_API_VERSION: str
    PRODUCT_SERVICE_URL_API_VERSION: str
    NOTIFICATION_SERVICE_URL_API_VERSION: str
    ORDER_SERVICE_URL_API_VERSION: str
    PAYMENT_SERVICE_URL_API_VERSION: str
    CART_SERVICE_URL_API_VERSION: str
    SHIPPING_SERVICE_URL_API_VERSION: str
    WISHLIST_SERVICE_URL_API_VERSION: str
    SUPPLIER_SERVICE_URL_API_VERSION: str

    # Redis configuration
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    APIGATEWAY_SERVICE_REDIS_DB: int
    # Shared by user-service (writer) and api-gateway (reader) so a revoked
    # session is visible to whichever process authenticates the next request.
    SESSION_REGISTRY_REDIS_DB: int = 13

    # Ed25519 keys as PEM, unwrapped by the accessor properties below. A
    # private key is optional so a process that never signs runs without it.
    # User tokens: user-service signs them; it and the gateway verify them.
    USER_TOKEN_PUBLIC_KEY: str | None = None
    USER_TOKEN_ISSUER: str = "user-service"
    USER_TOKEN_AUDIENCE: str = "ecommerce-api"

    # The gateway signs an assertion for every request it proxies; each
    # service verifies it before trusting the caller.
    GATEWAY_ASSERTION_PRIVATE_KEY: SecretStr | None = None
    GATEWAY_ASSERTION_ISSUER: str = "api-gateway"
    GATEWAY_ASSERTION_AUDIENCE: str = "internal-services"
    GATEWAY_ASSERTION_TTL_SECONDS: int = Field(default=60, gt=0, le=300)

    # Per-service circuit breaker in the gateway.
    GATEWAY_BREAKER_FAILURE_THRESHOLD: int = Field(default=5, ge=1)
    GATEWAY_BREAKER_RECOVERY_SECONDS: float = Field(default=30.0, gt=0)

    # User sessions
    TOKEN_TIME_DELTA_MINUTES: int
    REFRESH_TOKEN_TIME_DELTA_DAYS: int

    # CORS
    CORS_ALLOWED_ORIGINS: list[str]
    CORS_ALLOW_CREDENTIALS: bool
    CORS_ALLOWED_METHODS: list[str]
    CORS_ALLOWED_HEADERS: list[str]

    MISSING_SECRET_HINT: ClassVar[str] = (
        "{name} is not configured for this service. Secrets are optional so "
        "a process that never uses one need not hold it; put it in this "
        "service's Vault path (secret/ecommerce/<service>) if the feature is "
        "meant to work here."
    )

    @staticmethod
    def _reveal(value: "SecretStr | str | None", name: str) -> str:
        """Unwrap a secret at the point of use, or say plainly what is missing.

        Keeping these as SecretStr means the value never renders in a log line,
        a traceback, or a settings repr — the three places a key most often
        escapes without anyone deciding to expose it.
        """
        if value is None:
            raise RuntimeError(Settings.MISSING_SECRET_HINT.format(name=name))
        # A plain string is accepted so a test double or an alternative
        # settings source is not forced to wrap every value.
        if isinstance(value, str):
            return value
        return value.get_secret_value()

    @property
    def USER_TOKEN_VERIFYING_KEY_PEM(self) -> str:
        return self._reveal(self.USER_TOKEN_PUBLIC_KEY, "USER_TOKEN_PUBLIC_KEY")

    @property
    def GATEWAY_ASSERTION_SIGNING_KEY_PEM(self) -> str:
        return self._reveal(
            self.GATEWAY_ASSERTION_PRIVATE_KEY, "GATEWAY_ASSERTION_PRIVATE_KEY"
        )

    # Other
    SECRET_ROLE: str

    # --------------API-GATEWAY-----------------------

    @property
    def APIGATEWAY_SERVICE_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.APIGATEWAY_SERVICE_REDIS_DB}"

    @property
    def FULL_USER_SERVICE_URL(self) -> str:
        return f"{self.USER_SERVICE_URL}{self.USER_SERVICE_URL_API_VERSION}"

    @property
    def FULL_PRODUCT_SERVICE_URL(self) -> str:
        return f"{self.PRODUCT_SERVICE_URL}{self.PRODUCT_SERVICE_URL_API_VERSION}"

    @property
    def FULL_NOTIFICATION_SERVICE_URL(self) -> str:
        return f"{self.NOTIFICATION_SERVICE_URL}{self.NOTIFICATION_SERVICE_URL_API_VERSION}"

    @property
    def FULL_ORDER_SERVICE_URL(self) -> str:
        return f"{self.ORDER_SERVICE_URL}{self.ORDER_SERVICE_URL_API_VERSION}"

    @property
    def FULL_PAYMENT_SERVICE_URL(self) -> str:
        return f"{self.PAYMENT_SERVICE_URL}{self.PAYMENT_SERVICE_URL_API_VERSION}"

    @property
    def FULL_CART_SERVICE_URL(self) -> str:
        return f"{self.CART_SERVICE_URL}{self.CART_SERVICE_URL_API_VERSION}"

    @property
    def FULL_SHIPPING_SERVICE_URL(self) -> str:
        return f"{self.SHIPPING_SERVICE_URL}{self.SHIPPING_SERVICE_URL_API_VERSION}"

    @property
    def FULL_WISHLIST_SERVICE_URL(self) -> str:
        return f"{self.WISHLIST_SERVICE_URL}{self.WISHLIST_SERVICE_URL_API_VERSION}"

    @property
    def SESSION_REGISTRY_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.SESSION_REGISTRY_REDIS_DB}"

    @property
    def FULL_SUPPLIER_SERVICE_URL(self) -> str:
        return f"{self.SUPPLIER_SERVICE_URL}{self.SUPPLIER_SERVICE_URL_API_VERSION}"


class TestSettings(BaseSettings):
    API: str = "/api/v1"

    # ── User ────────────────────────────────────────────────────────────────
    TEST_USER_ID: UUID = uuid4()
    TEST_ADMIN_ID: UUID = uuid4()
    TEST_USER_ROLE: str = "user"
    TEST_ADMIN_ROLE: str = "admin"  # the only admin role users.ck_users_role allows
    TEST_EMAIL: str = "test@example.com"
    TEST_ADMIN_EMAIL: str = "admin@example.com"

    # ── Product ─────────────────────────────────────────────────────────────
    TEST_PRODUCT_ID: UUID = uuid4()
    TEST_CATEGORY_ID: UUID = uuid4()
    TEST_REVIEW_ID: UUID = uuid4()
    TEST_IMAGE_ID: UUID = uuid4()

    # ── Order ────────────────────────────────────────────────────────────────
    TEST_ORDER_ID: UUID = uuid4()

    # ── Payment ──────────────────────────────────────────────────────────────
    TEST_PAYMENT_ID: UUID = uuid4()

    # ── Notification ─────────────────────────────────────────────────────────
    TEST_NOTIFICATION_ID: UUID = uuid4()

    MOCK_UPSTREAM_RESPONSE_BODY: dict[str, str] = {
        "status": "ok",
        "data": "upstream_result",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_test_settings() -> TestSettings:
    return TestSettings()

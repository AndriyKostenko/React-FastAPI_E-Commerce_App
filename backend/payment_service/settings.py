"""payment-service's settings: only the fields it, and the infrastructure it
uses, read. Names match the keys in the backend config file and in this
service's Vault path, so every value is still set where it was before.
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import AliasChoices, Field, SecretStr
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

    PAYMENT_SERVICE_APP_PORT: int

    DEBUG_MODE: bool

    # PostgreSQL connection pool tuning — used by PoolSettingsCalculator
    PG_MAX_CONNECTIONS: int = 100  # must match postgresql.conf max_connections
    PG_RESERVED_CONNECTIONS: int = 5  # reserved for superuser / admin / monitoring
    PG_DB_SERVICES_COUNT: int = (
        9  # number of microservices sharing the same Postgres instance
    )

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

    PAYMENT_SERVICE_URL_API_VERSION: str

    # Database configuration
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    PAYMENT_SERVICE_DB: str

    PAYMENT_SERVICE_TEST_DB: str

    # RabbitMQ configuration
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    # Redis configuration
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    PAYMENT_SERVICE_REDIS_DB: int

    IDEMPOTENCY_EVENT_SERVICE_HOURS: int

    # The gateway signs an assertion for every request it proxies; each
    # service verifies it before trusting the caller.
    GATEWAY_ASSERTION_PUBLIC_KEY: str | None = None
    GATEWAY_ASSERTION_ISSUER: str = "api-gateway"
    GATEWAY_ASSERTION_AUDIENCE: str = "internal-services"

    # Direct service-to-service calls (see shared.auth.service_assertion):
    # order-service signs its calls to product-, supplier- and payment-service;
    # supplier-service signs its calls to product-service (the hourly CJ stock
    # refresh reads which CJ products we sell). The caller holds the private
    # key, the services it calls the public one.
    ORDER_SERVICE_ASSERTION_PUBLIC_KEY: str | None = None

    # Stripe. Optional so a service that never charges a card can run
    # without holding the key at all — see MISSING_SECRET_HINT below.
    # Named for what it is, test or live. The old STRIPE_TEST_SECRET_KEY name
    # is still read, so an existing env file keeps working.
    STRIPE_SECRET_KEY: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("STRIPE_SECRET_KEY", "STRIPE_TEST_SECRET_KEY"),
    )
    STRIPE_WEBHOOK_SECRET: SecretStr | None = None

    # Calls to Stripe
    STRIPE_REQUEST_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=120)
    STRIPE_MAX_NETWORK_RETRIES: int = Field(default=2, ge=0, le=5)
    # Tax code for the goods sold; None uses the account's preset code.
    # T-shirts are clothing: txcd_30011000.
    STRIPE_TAX_PRODUCT_TAX_CODE: str | None = None

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
    def STRIPE_API_KEY(self) -> str:
        return self._reveal(self.STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")

    @property
    def STRIPE_WEBHOOK_SIGNING_SECRET(self) -> str:
        return self._reveal(self.STRIPE_WEBHOOK_SECRET, "STRIPE_WEBHOOK_SECRET")

    @property
    def GATEWAY_ASSERTION_VERIFYING_KEY_PEM(self) -> str:
        return self._reveal(
            self.GATEWAY_ASSERTION_PUBLIC_KEY, "GATEWAY_ASSERTION_PUBLIC_KEY"
        )

    # Other
    SECRET_ROLE: str
    POLLING_INTERVAL_FROM_DB: int | float = 5

    # --------------RABBITMQ-----------------------

    @property
    def RABBITMQ_BROKER_URL(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}"

    # ---------------PAYMENT-SERVICE-------------------

    @property
    def PAYMENT_SERVICE_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.PAYMENT_SERVICE_DB}"

    @property
    def PAYMENT_SERVICE_TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.PAYMENT_SERVICE_TEST_DB}"

    @property
    def PAYMENT_SERVICE_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.PAYMENT_SERVICE_REDIS_DB}"

    @property
    def FULL_STRIPE_WEBHOOK_ENDPOINT(self) -> str:
        return f"https://{self.APP_HOST}{self.PAYMENT_SERVICE_URL_API_VERSION}/payments/webhook"


class TestSettings(BaseSettings):
    # ── Common ──────────────────────────────────────────────────────────────
    TEST_DATETIME: datetime = datetime(2024, 1, 1, 12, 0, 0)
    API: str = "/api/v1"

    # ── User ────────────────────────────────────────────────────────────────
    TEST_USER_ID: UUID = uuid4()
    TEST_EMAIL: str = "test@example.com"

    # ── Order ────────────────────────────────────────────────────────────────
    TEST_ORDER_ID: UUID = uuid4()
    TEST_CURRENCY: str = "usd"

    # ── Payment ──────────────────────────────────────────────────────────────
    TEST_PAYMENT_ID: UUID = uuid4()
    TEST_STRIPE_INTENT_ID: str = "pi_test_abc123"
    TEST_CLIENT_SECRET: str = "pi_test_abc123_secret_xyz"
    TEST_AMOUNT_CENTS: int = 9999  # payment amount in cents

    MOCK_PAYMENT_INTENT_RESULT: dict = {
        "client_secret": TEST_CLIENT_SECRET,
        "stripe_payment_intent_id": TEST_STRIPE_INTENT_ID,
        "payment_id": str(TEST_PAYMENT_ID),
        "order_id": str(TEST_ORDER_ID),
        "amount": TEST_AMOUNT_CENTS,
        "currency": TEST_CURRENCY,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_test_settings() -> TestSettings:
    return TestSettings()

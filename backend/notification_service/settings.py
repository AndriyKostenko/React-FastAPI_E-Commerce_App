"""notification-service's settings: only the fields it, and the infrastructure it
uses, read. Names match the keys in the backend config file and in this
service's Vault path, so every value is still set where it was before.
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from infrastructure.vault import VaultSettingsSource

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
    FRONTEND_URL: str

    NOTIFICATION_SERVICE_APP_PORT: int

    DEBUG_MODE: bool

    # Connections one process of this service may hold: pool_size + max_overflow.
    # The defaults are an API process's (one gunicorn worker). compose and
    # dev.sh give consumers, outbox and saga workers 1 + 1, and taskiq workers
    # 1 + 0 (each task opens its own engine). The sum over every process must
    # fit Postgres's max_connections: `./local/dev.sh pool-budget` checks it.
    DB_POOL_SIZE: int = Field(default=3, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=2, ge=0)
    # Seconds a request waits for a free connection before failing.
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=5, ge=1)

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

    NOTIFICATION_SERVICE_URL_API_VERSION: str

    # Database configuration
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    NOTIFICATION_SERVICE_DB: str

    NOTIFICATION_SERVICE_TEST_DB: str

    # RabbitMQ configuration
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    # Redis configuration
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    NOTIFICATION_SERVICE_REDIS_DB: int

    NOTIFICATION_SERVICE_REDIS_BACKEND_RESULT_DB: int

    NOTIFICATION_SERVICE_REDIS_PREFIX: str

    IDEMPOTENCY_EVENT_SERVICE_HOURS: int

    # The gateway signs an assertion for every request it proxies; each
    # service verifies it before trusting the caller.
    GATEWAY_ASSERTION_PUBLIC_KEY: str | None = None
    GATEWAY_ASSERTION_ISSUER: str = "api-gateway"
    GATEWAY_ASSERTION_AUDIENCE: str = "internal-services"

    # User sessions
    RESET_TOKEN_EXPIRY_MINUTES: int

    # Email
    MAIL_USERNAME: str
    # Held by notification-service only; read through MAIL_SERVER_PASSWORD.
    MAIL_PASSWORD: SecretStr | None = None
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool
    MAIL_DEBUG: bool
    MAIL_FROM: str
    MAIL_FROM_NAME: str
    USE_CREDENTIALS: bool
    VALIDATE_CERTS: bool
    # Where operational alerts (payment disputes, return requests) are emailed. Unset: logged only.
    ADMIN_ALERT_EMAIL: str | None = None

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
    def GATEWAY_ASSERTION_VERIFYING_KEY_PEM(self) -> str:
        return self._reveal(
            self.GATEWAY_ASSERTION_PUBLIC_KEY, "GATEWAY_ASSERTION_PUBLIC_KEY"
        )

    @property
    def MAIL_SERVER_PASSWORD(self) -> str:
        return self._reveal(self.MAIL_PASSWORD, "MAIL_PASSWORD")

    # Other
    SECRET_ROLE: str

    # --------------RABBITMQ-----------------------

    @property
    def RABBITMQ_BROKER_URL(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}"

    # ---------------NOTIFICATION-SERVICE---------------

    @property
    def NOTIFICATION_SERVICE_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.NOTIFICATION_SERVICE_DB}"

    @property
    def NOTIFICATION_SERVICE_TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.NOTIFICATION_SERVICE_TEST_DB}"

    @property
    def NOTIFICATION_SERVICE_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.NOTIFICATION_SERVICE_REDIS_DB}"

    @property
    def NOTIFICATION_SERVICE_REDIS_RESULT_BACKEND_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.NOTIFICATION_SERVICE_REDIS_BACKEND_RESULT_DB}"


class TestSettings(BaseSettings):
    # ── Common ──────────────────────────────────────────────────────────────
    TEST_DATETIME: datetime = datetime(2024, 1, 1, 12, 0, 0)
    API: str = "/api/v1"

    # ── User ────────────────────────────────────────────────────────────────
    TEST_USER_ID: UUID = uuid4()
    TEST_EMAIL: str = "test@example.com"

    # ── Order ────────────────────────────────────────────────────────────────
    TEST_ORDER_ID: UUID = uuid4()

    # ── Notification ─────────────────────────────────────────────────────────
    TEST_NOTIFICATION_ID: UUID = uuid4()
    TEST_NOTIFICATION_TYPE: str = "user.registered"
    TEST_MESSAGE: str = "Welcome! Please verify your email address."
    TEST_EVENT_ID: str = str(uuid4())

    # ── Mock result dicts (for JSON response assertions) ─────────────────────
    MOCK_NOTIFICATION_RESULT: dict = {
        "id": str(TEST_NOTIFICATION_ID),
        "user_id": str(TEST_USER_ID),
        "message": TEST_MESSAGE,
        "notification_type": TEST_NOTIFICATION_TYPE,
        "is_read": False,
        "date_created": TEST_DATETIME.isoformat(),
        "date_updated": None,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_test_settings() -> TestSettings:
    return TestSettings()

"""user-service's settings: only the fields it, and the infrastructure it
uses, read. Names match the keys in the backend config file and in this
service's Vault path, so every value is still set where it was before.
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal
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

    USER_SERVICE_APP_PORT: int

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

    USER_SERVICE_URL_API_VERSION: str

    # Database configuration
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    USER_SERVICE_DB: str

    USER_SERVICE_TEST_DB: str

    # RabbitMQ configuration
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    # Redis configuration
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    USER_SERVICE_REDIS_DB: int
    # Shared by user-service (writer) and api-gateway (reader) so a revoked
    # session is visible to whichever process authenticates the next request.
    SESSION_REGISTRY_REDIS_DB: int = 13

    # Ed25519 keys as PEM, unwrapped by the accessor properties below. A
    # private key is optional so a process that never signs runs without it.
    # User tokens: user-service signs them; it and the gateway verify them.
    USER_TOKEN_PRIVATE_KEY: SecretStr | None = None
    USER_TOKEN_PUBLIC_KEY: str | None = None
    USER_TOKEN_ISSUER: str = "user-service"
    USER_TOKEN_AUDIENCE: str = "ecommerce-api"

    # The gateway signs an assertion for every request it proxies; each
    # service verifies it before trusting the caller.
    GATEWAY_ASSERTION_PUBLIC_KEY: str | None = None
    GATEWAY_ASSERTION_ISSUER: str = "api-gateway"
    GATEWAY_ASSERTION_AUDIENCE: str = "internal-services"

    # User sessions
    TOKEN_TYPE: str
    TOKEN_TIME_DELTA_MINUTES: int
    REFRESH_TOKEN_TIME_DELTA_DAYS: int
    RESET_TOKEN_EXPIRY_MINUTES: int
    VERIFICATION_TOKEN_EXPIRY_MINUTES: int
    CRYPT_CONTEXT_SCHEME: str

    # CORS
    CORS_ALLOWED_ORIGINS: list[str]
    CORS_ALLOW_CREDENTIALS: bool
    CORS_ALLOWED_METHODS: list[str]
    CORS_ALLOWED_HEADERS: list[str]

    # Google OAuth
    GOOGLE_CLIENT_ID: str

    # Cloudflare Turnstile: register, login and forgot-password must carry a
    # token the storefront's widget issued (service_layer/human_check.py). The
    # secret is in this service's Vault path; locally dev.sh stores Cloudflare's
    # always-pass test secret there (it accepts any token, the test widget's
    # dummy one included). Production needs the site's own secret, which
    # refuses dummy tokens, and the matching site key in the frontend's
    # NEXT_PUBLIC_TURNSTILE_SITE_KEY.
    TURNSTILE_SECRET_KEY: SecretStr | None = None

    # Stored email addresses are encrypted (infrastructure/utils/email_cipher.py):
    # EMAIL_ENCRYPTION_KEY encrypts, and EMAIL_ENCRYPTION_OLD_KEYS (comma
    # separated) still decrypt what earlier keys wrote, after a rotation.
    # EMAIL_LOOKUP_KEY keys the hash that finds a row by address. Each is 32
    # random bytes, base64, in this service's Vault path; dev.sh generates them
    # on `infra up`. Losing a key loses every address it encrypted: back it up.
    EMAIL_ENCRYPTION_KEY: SecretStr
    EMAIL_ENCRYPTION_OLD_KEYS: SecretStr | None = None
    EMAIL_LOOKUP_KEY: SecretStr

    # New accounts: refuse throwaway-inbox domains and, with the check on,
    # domains that cannot receive mail (a DNS lookup, at most this many seconds).
    EMAIL_DELIVERABILITY_CHECK: bool = True
    EMAIL_DNS_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0, le=10)
    # A registration for an email that already has an account mails that
    # account (a fresh verification link, or "someone tried to sign up") at
    # most once in this many minutes, so the form cannot be used to flood it.
    SIGNUP_NOTICE_INTERVAL_MINUTES: int = Field(default=60, ge=1)

    # Admin passkeys (WebAuthn), checked by user-service. Admin accounts sign
    # in only with a passkey, and only on the admin panel's own origin: a
    # passkey is bound to WEBAUTHN_RP_ID (a host name, ports ignored) and every
    # signed response names its origin, which must be one of WEBAUTHN_ORIGINS.
    # Locally the panel is http://localhost:3001; in production it is the
    # private host admin-js is reached on (it is never routed publicly).
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "E-Commerce Admin"
    WEBAUTHN_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3001"])
    # The admin panel's base URL, for the enrolment link the owner is given.
    ADMIN_PANEL_URL: str = "http://localhost:3001/admin"
    PASSKEY_ENROLMENT_TTL_MINUTES: int = Field(default=15, ge=1, le=60)
    PASSKEY_CHALLENGE_TTL_SECONDS: int = Field(default=300, ge=30, le=600)

    # Avatars live in the public catalogue bucket under ``avatars/`` -- the
    # only prefix user-service's key may touch. The row keeps the object key;
    # responses add AWS_S3_CATALOGUE_PUBLIC_BASE_URL. With ``local`` (no object
    # store) avatar uploads are refused; nothing else needs storage. Checked
    # where used, so the service starts without them.
    OBJECT_STORAGE_BACKEND: Literal["local", "s3"] = "local"
    AWS_S3_CATALOGUE_BUCKET: str | None = None
    AWS_S3_CATALOGUE_PUBLIC_BASE_URL: str | None = None
    AWS_S3_REGION: str | None = None
    AWS_S3_ENDPOINT_URL: str | None = None
    # Static keys exist for S3-compatible servers (the local SeaweedFS) only;
    # unset in AWS, where the default credential chain is used.
    AWS_S3_ACCESS_KEY_ID: SecretStr | None = None
    AWS_S3_SECRET_ACCESS_KEY: SecretStr | None = None
    AVATAR_MAX_UPLOAD_BYTES: int = Field(default=5 * 1024 * 1024, ge=64 * 1024, le=20 * 1024 * 1024)
    AVATAR_SIZE_PX: int = Field(default=512, ge=64, le=2048)

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
    def USER_TOKEN_SIGNING_KEY_PEM(self) -> str:
        return self._reveal(self.USER_TOKEN_PRIVATE_KEY, "USER_TOKEN_PRIVATE_KEY")

    @property
    def USER_TOKEN_VERIFYING_KEY_PEM(self) -> str:
        return self._reveal(self.USER_TOKEN_PUBLIC_KEY, "USER_TOKEN_PUBLIC_KEY")

    @property
    def TURNSTILE_SECRET(self) -> str:
        return self._reveal(self.TURNSTILE_SECRET_KEY, "TURNSTILE_SECRET_KEY")

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

    # --------------USER-SERVICE---------------------

    @property
    def USER_SERVICE_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.USER_SERVICE_DB}"

    @property
    def USER_SERVICE_TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.USER_SERVICE_TEST_DB}"

    @property
    def USER_SERVICE_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.USER_SERVICE_REDIS_DB}"

    @property
    def SESSION_REGISTRY_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.SESSION_REGISTRY_REDIS_DB}"


class TestSettings(BaseSettings):
    # ── Common ──────────────────────────────────────────────────────────────
    TEST_DATETIME: datetime = datetime(2024, 1, 1, 12, 0, 0)
    API: str = "/api/v1"

    # ── Auth / Token settings ────────────────────────────────────────────────
    CRYPT_CONTEXT_SCHEME: str = "bcrypt"
    SECRET_KEY: str = "test-secret-key-not-for-production"
    REFRESH_TOKEN_TIME_DELTA_DAYS: int = 7

    # ── User ────────────────────────────────────────────────────────────────
    TEST_USER_ID: UUID = uuid4()
    TEST_USER_ROLE: str = "user"
    TEST_ADMIN_ROLE: str = "admin"  # the only admin role users.ck_users_role allows
    TEST_NAME: str = "Test User"
    TEST_EMAIL: str = "test@example.com"
    TEST_PHONE_NUMBER: str = "4372998642"
    TEST_PASSWORD: str = "Password123!"
    TEST_HASHED_PW: str = "$2b$12$fakehashfortesting000000000000000000"

    # ── Human check ──────────────────────────────────────────────────────────
    # The token Cloudflare's test widget issues; production secrets refuse it.
    CAPTCHA_TOKEN: str = "XXXX.DUMMY.TOKEN.XXXX"

    # ── Auth request payload helpers ─────────────────────────────────────────
    REGISTER_PAYLOAD: dict[str, str] = {
        "name": "Test User",
        "email": "test@example.com",
        "password": "Password123!",
        "captcha_token": "XXXX.DUMMY.TOKEN.XXXX",
    }
    LOGIN_DATA: dict[str, str] = {
        "username": "test@example.com",
        "password": "secret123",
        "captcha_token": "XXXX.DUMMY.TOKEN.XXXX",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_test_settings() -> TestSettings:
    return TestSettings()

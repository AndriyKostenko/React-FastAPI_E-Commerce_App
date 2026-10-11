"""product-service's settings: only the fields it, and the infrastructure it
uses, read. Names match the keys in the backend config file and in this
service's Vault path, so every value is still set where it was before.
"""

from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal
from uuid import UUID, uuid4

from pydantic import AliasChoices, Field, SecretStr
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
    WEBSITE_NAME: str
    APP_HOST: str
    FRONTEND_URL: str
    MEDIA_ROOT: str

    PRODUCT_SERVICE_APP_PORT: int

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

    PRODUCT_SERVICE_URL_API_VERSION: str

    # Database configuration
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    PRODUCT_SERVICE_DB: str

    PRODUCT_SERVICE_TEST_DB: str

    # RabbitMQ configuration
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    # Redis configuration
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    PRODUCT_SERVICE_REDIS_DB: int

    PRODUCT_SERVICE_REDIS_PREFIX: str

    IDEMPOTENCY_EVENT_SERVICE_HOURS: int

    # No longer an auth secret; only the artwork-signing fallback reads it.
    SECRET_KEY: SecretStr | None = None

    # The gateway signs an assertion for every request it proxies; each
    # service verifies it before trusting the caller.
    GATEWAY_ASSERTION_PUBLIC_KEY: str | None = None
    GATEWAY_ASSERTION_ISSUER: str = "api-gateway"
    GATEWAY_ASSERTION_AUDIENCE: str = "internal-services"

    # Direct service-to-service calls (see infrastructure.auth.service_assertion):
    # order-service signs its calls to product-, supplier- and payment-service;
    # supplier-service signs its calls to product-service (the hourly CJ stock
    # refresh reads which CJ products we sell). The caller holds the private
    # key, the services it calls the public one.
    ORDER_SERVICE_ASSERTION_PUBLIC_KEY: str | None = None
    SUPPLIER_SERVICE_ASSERTION_PUBLIC_KEY: str | None = None

    # CORS
    CORS_ALLOWED_ORIGINS: list[str]
    CORS_ALLOW_CREDENTIALS: bool
    CORS_ALLOWED_METHODS: list[str]
    CORS_ALLOWED_HEADERS: list[str]

    # OpenRouter image generation
    OPENROUTER_API_KEY: SecretStr | None = None
    OPENROUTER_BASE_URL: str
    OPENROUTER_IMAGE_MODEL: str
    OPENROUTER_IMAGE_SIZE: str = "1024x1024"
    OPENROUTER_IMAGE_ASPECT_RATIO: str = "1:1"
    # Generation is for signed-in users only; each gets this many per window.
    PRODUCT_IMAGE_GENERATION_LIMIT: int = 10
    PRODUCT_IMAGE_GENERATION_WINDOW_HOURS: int = 24
    # Background removal (rembg). The model must be licensed for commercial
    # use — rembg's own default, bria-rmbg, is non-commercial.
    PRODUCT_IMAGE_BG_REMOVAL_MODEL: str = "isnet-general-use"
    # A cutout keeping less than this share of opaque pixels means the model
    # removed the design itself, so the job fails instead of printing nothing.
    PRODUCT_IMAGE_BG_MIN_FOREGROUND_RATIO: float = Field(default=0.01, gt=0, lt=1)

    # Dedicated production resolution; kept separate from the older preview
    # setting so an existing 1024x1024 environment cannot silently create
    # artwork that is too small to print.
    PRINT_IMAGE_GENERATION_SIZE: str = "4K"

    # Object storage for every image: ``local`` (disk under MEDIA_ROOT /
    # RETURN_EVIDENCE_ROOT) or ``s3``. Two buckets, never mixed:
    #   catalogue -- public-read: product, variant and category images (CJ
    #                copies and admin uploads), served from
    #                AWS_S3_CATALOGUE_PUBLIC_BASE_URL;
    #   private   -- generated designs and return photos, reached only through
    #                presigned URLs or the owning service.
    # The bucket settings are checked where they are used, so a service that
    # never touches storage starts without them.
    OBJECT_STORAGE_BACKEND: Literal["local", "s3"] = Field(
        default="local",
        validation_alias=AliasChoices("OBJECT_STORAGE_BACKEND", "ARTWORK_STORAGE_BACKEND"),
    )
    ARTWORK_SIGNING_SECRET: SecretStr | None = None
    AWS_S3_PRIVATE_BUCKET: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AWS_S3_PRIVATE_BUCKET", "AWS_S3_ARTWORK_BUCKET"),
    )
    AWS_S3_CATALOGUE_BUCKET: str | None = None
    # Public origin of the catalogue bucket (CloudFront in production, the
    # local S3 server's bucket URL in development); keys are appended to it.
    AWS_S3_CATALOGUE_PUBLIC_BASE_URL: str | None = None
    AWS_S3_REGION: str | None = None
    AWS_S3_ENDPOINT_URL: str | None = None
    # Static keys exist for S3-compatible servers (the local SeaweedFS) only.
    # Unset in AWS, where the default credential chain picks up the workload
    # role; they are Vault secrets, one pair per service.
    AWS_S3_ACCESS_KEY_ID: SecretStr | None = None
    AWS_S3_SECRET_ACCESS_KEY: SecretStr | None = None
    # CloudFront in front of the *private* bucket for design previews (Origin
    # Access Control); without it previews are presigned GETs.
    AWS_S3_PUBLIC_BASE_URL: str | None = None
    AWS_S3_KMS_KEY_ID: str | None = None
    AWS_S3_PRESIGNED_URL_TTL_SECONDS: int = Field(default=3600, ge=60, le=604800)
    # CJ catalogue images copied into the catalogue bucket.
    CATALOGUE_IMAGE_MAX_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)
    CATALOGUE_IMAGE_MIRROR_BATCH: int = Field(default=50, gt=0, le=1000)
    CATALOGUE_IMAGE_MIRROR_MAX_ATTEMPTS: int = Field(default=10, gt=0)
    # Admin uploads (product images, category icons).
    CATALOGUE_UPLOAD_MAX_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)

    # 2250x2700 supports a 15x18 inch maximum garment area at 150 effective
    # DPI. The preferred provider request is 4K; no artificial upscaling is
    # performed by the storage layer.
    PRINT_IMAGE_MIN_WIDTH_PX: int = Field(default=2250, ge=1, le=30_000)
    PRINT_IMAGE_MIN_HEIGHT_PX: int = Field(default=2700, ge=1, le=30_000)
    PRINT_IMAGE_MAX_DIMENSION_PX: int = Field(default=6000, ge=1, le=30_000)
    PRINT_IMAGE_MAX_PIXELS: int = Field(default=36_000_000, ge=1)
    PRINT_IMAGE_MAX_BYTES: int = Field(default=50_000_000, ge=1)
    PRINT_IMAGE_EMBEDDED_DPI: int = Field(default=300, ge=72, le=1200)

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
    def OPENROUTER_KEY(self) -> str:
        return self._reveal(self.OPENROUTER_API_KEY, "OPENROUTER_API_KEY")

    @property
    def ARTWORK_SIGNING_KEY(self) -> str:
        """Use a dedicated key when configured, with a migration-safe fallback."""

        if self.ARTWORK_SIGNING_SECRET is not None:
            return self.ARTWORK_SIGNING_SECRET.get_secret_value()
        return self._reveal(self.SECRET_KEY, "ARTWORK_SIGNING_SECRET (or its SECRET_KEY fallback)")

    # Other
    SECRET_ROLE: str
    POLLING_INTERVAL_FROM_DB: int | float = 5
    CUSTOM_TSHIRT_BASE_PRICE: float

    # CJDropshipping
    CJ_DROPSHIPPING_DEFAULT_CATEGORY_NAME: str = "t-shirts"

    # Storefront pricing of supplier goods. CJ prices in USD while the store
    # sells in CAD; keep the rate current, since it also converts freight.
    CJ_USD_TO_CAD_RATE: Decimal = Field(default=Decimal("1.38"), gt=0)
    # Where the USD->CAD rate comes from: the Bank of Canada's daily rate
    # (cached; CJ_USD_TO_CAD_RATE is then only the fallback), or "fixed".
    CJ_FX_SOURCE: Literal["bank_of_canada", "fixed"] = "bank_of_canada"
    # Retail never drops below CJ's cost times this multiplier.
    CJ_PRICE_MARKUP_MULTIPLIER: Decimal = Field(default=Decimal("2.00"), ge=1)

    # --------------RABBITMQ-----------------------

    @property
    def RABBITMQ_BROKER_URL(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}"

    # ---------------PRODUCT-SERVICE-------------------

    @property
    def PRODUCT_SERVICE_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.PRODUCT_SERVICE_DB}"

    @property
    def PRODUCT_SERVICE_TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.PRODUCT_SERVICE_TEST_DB}"

    @property
    def PRODUCT_SERVICE_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.PRODUCT_SERVICE_REDIS_DB}"


class TestSettings(BaseSettings):
    # ── Common ──────────────────────────────────────────────────────────────
    TEST_DATETIME: datetime = datetime(2024, 1, 1, 12, 0, 0)
    API: str = "/api/v1"

    # ── User ────────────────────────────────────────────────────────────────
    TEST_USER_ID: UUID = uuid4()

    # ── Product ─────────────────────────────────────────────────────────────
    TEST_PRODUCT_ID: UUID = uuid4()
    TEST_CATEGORY_ID: UUID = uuid4()
    TEST_REVIEW_ID: UUID = uuid4()


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_test_settings() -> TestSettings:
    return TestSettings()

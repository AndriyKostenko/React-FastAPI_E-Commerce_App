"""supplier-service's settings: only the fields it, and the infrastructure it
uses, read. Names match the keys in the backend config file and in this
service's Vault path, so every value is still set where it was before.
"""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

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

    SUPPLIER_SERVICE_APP_PORT: int

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

    # Service URLs
    PRODUCT_SERVICE_URL: str

    API_GATEWAY_SERVICE_URL_API_VERSION: str
    PRODUCT_SERVICE_URL_API_VERSION: str
    SUPPLIER_SERVICE_URL_API_VERSION: str

    # Database configuration
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    SUPPLIER_SERVICE_DB: str

    SUPPLIER_SERVICE_TEST_DB: str

    # RabbitMQ configuration
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    # Redis configuration
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    SUPPLIER_SERVICE_REDIS_DB: int

    SUPPLIER_SERVICE_REDIS_PREFIX: str

    IDEMPOTENCY_EVENT_SERVICE_HOURS: int

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
    SUPPLIER_SERVICE_ASSERTION_PRIVATE_KEY: SecretStr | None = None

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
    def CJ_API_KEY(self) -> str:
        return self._reveal(self.CJ_DROPSHIPPING_API_KEY, "CJ_DROPSHIPPING_API_KEY")

    @property
    def CJ_WEBHOOK_SIGNING_KEY(self) -> str:
        return self._reveal(self.CJ_DROPSHIPPING_OPEN_ID, "CJ_DROPSHIPPING_OPEN_ID")

    # Other
    SECRET_ROLE: str
    POLLING_INTERVAL_FROM_DB: int | float = 5

    # CJDropshipping
    CJ_DROPSHIPPING_API_KEY: SecretStr | None = None
    CJ_DROPSHIPPING_ACCESS_TOKEN_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/authentication/getAccessToken"
    )
    CJ_DROPSHIPPING_PRODUCT_LIST_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/product/listV2"
    )
    CJ_DROPSHIPPING_PRODUCT_INFO_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/product/query"
    )
    CJ_DROPSHIPPING_INVENTORY_URL: str = "https://developers.cjdropshipping.com/api2.0/v1/product/stock/getInventoryByPid"
    CJ_DROPSHIPPING_VARIANT_INVENTORY_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/product/stock/queryByVid"
    )
    CJ_DROPSHIPPING_DEFAULT_CATEGORY_NAME: str = "t-shirts"
    CJ_DROPSHIPPING_TSHIRT_CATEGORY_IDS: list[str] = Field(default_factory=list)
    # The most CJ list products one sync run examines (and so at most imports);
    # supplier config "max_products" overrides it. Each costs two CJ calls per
    # run (details, China stock) and one more every hour (the stock refresh),
    # all from the one ~1 call/1.1 s budget checkout shares.
    CJ_DROPSHIPPING_SYNC_MAX_PRODUCTS: int = Field(default=200, ge=1)

    # Storefront pricing of supplier goods. CJ prices in USD while the store
    # sells in CAD; keep the rate current, since it also converts freight.
    CJ_USD_TO_CAD_RATE: Decimal = Field(default=Decimal("1.38"), gt=0)
    # Where the USD->CAD rate comes from: the Bank of Canada's daily rate
    # (cached; CJ_USD_TO_CAD_RATE is then only the fallback), or "fixed".
    CJ_FX_SOURCE: Literal["bank_of_canada", "fixed"] = "bank_of_canada"
    # Retail never drops below CJ's cost times this multiplier.
    CJ_PRICE_MARKUP_MULTIPLIER: Decimal = Field(default=Decimal("2.00"), ge=1)

    # Live inventory verification before order confirmation
    CJ_DROPSHIPPING_VERIFY_INVENTORY: bool = True
    # Units held back from what CJ reports, per variant: covers units sold here
    # but not yet ordered from CJ when the stock is refreshed.
    CJ_DROPSHIPPING_INVENTORY_BUFFER: int = 0
    # Hourly stock refresh: products per stock-update event sent to product-service.
    CJ_STOCK_REFRESH_BATCH_SIZE: int = Field(default=100, ge=1, le=1000)
    CJ_DROPSHIPPING_VERIFY_RETRIES: int = 2
    # Transient-failure handling for every CJ call (retries apply to reads only).
    CJ_DROPSHIPPING_RETRY_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=6)
    CJ_DROPSHIPPING_BREAKER_FAILURE_THRESHOLD: int = Field(default=5, ge=1)
    CJ_DROPSHIPPING_BREAKER_RECOVERY_SECONDS: float = Field(default=60.0, gt=0)
    CJ_DROPSHIPPING_VERIFY_TIMEOUT_SECONDS: float = 10.0
    CJ_DROPSHIPPING_REQUEST_TIMEOUT_SECONDS: float = 30.0
    # CJ allows one request per second per account at our level (Free / sales
    # level 0-1; Plus 2/s, Prime 4/s, Advanced 6/s) and answers more with a
    # 429. Every supplier-service process shares one budget, kept in Redis.
    # The interval is 1/QPS plus a margin for network jitter.
    CJ_DROPSHIPPING_RATE_LIMIT_ENABLED: bool = True
    CJ_DROPSHIPPING_REQUEST_INTERVAL_SECONDS: float = Field(default=1.1, gt=0)
    # How long a call may wait for its slot before failing as "CJ unavailable,
    # retry later". Customer-facing calls (the API process) queue for up to
    # their whole wait; background work takes a slot only when about one
    # interval's queue is ahead, so it never keeps a customer waiting long.
    CJ_DROPSHIPPING_INTERACTIVE_MAX_WAIT_SECONDS: float = Field(default=3.0, ge=0)
    CJ_DROPSHIPPING_BACKGROUND_MAX_WAIT_SECONDS: float = Field(default=30.0, ge=0)

    # CJ Dropshipping order creation
    CJ_DROPSHIPPING_CREATE_ORDER_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/createOrderV2"
    )
    CJ_DROPSHIPPING_ORDER_DETAIL_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/getOrderDetail"
    )
    CJ_DROPSHIPPING_DELETE_ORDER_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/deleteOrder"
    )
    CJ_DROPSHIPPING_DEFAULT_LOGISTIC_NAME: str = "CJPacket"
    # Where CJ goods ship from (China warehouses only) and where the store sells
    # (Canada only) are fixed in contracts.shipping_region, not here:
    # the old CJ_DROPSHIPPING_DEFAULT_FROM_COUNTRY_CODE and
    # CJ_DROPSHIPPING_SUPPORTED_COUNTRY_CODES are no longer read.
    # 3 = create only. Confirmation and balance payment then run as separate,
    # individually recorded steps (see CJOrderPaymentService).
    CJ_DROPSHIPPING_PAY_TYPE: int = 3  # 1=page payment, 2=balance, 3=create only
    CJ_DROPSHIPPING_CONFIRM_ORDER_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/confirmOrder"
    )
    CJ_DROPSHIPPING_BALANCE_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/shopping/pay/getBalance"
    )
    CJ_DROPSHIPPING_PAY_BALANCE_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/shopping/pay/payBalance"
    )
    # CJ's bill may exceed the expected product cost plus quoted freight by this
    # fraction before payment is held for review instead of sent.
    CJ_ORDER_COST_TOLERANCE: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    # An unpaid CJ order is retried at this interval, and given up on (which
    # cancels the order and voids the customer's card hold) after the max wait.
    CJ_PAYMENT_RETRY_INTERVAL_MINUTES: int = Field(default=10, gt=0)
    CJ_PAYMENT_MAX_WAIT_HOURS: int = Field(default=24, gt=0)
    CJ_PAYMENT_BATCH_SIZE: int = Field(default=50, gt=0)
    # Longer than a full confirm -> pay walk with CJ timeouts and retries.
    CJ_PAYMENT_LEASE_MINUTES: int = Field(default=10, gt=0)
    CJ_DROPSHIPPING_PLATFORM: str = "Api"
    # CJ's sandbox: new CJ orders are created with isSandbox=1, which CJ fills
    # with a simulated payment and no real shipment. Payment then goes through
    # CJ's simulatePay instead of the wallet (decided per order, when it is
    # created), and `./local/dev.sh cj-sandbox` moves an order to shipped /
    # delivered. Never on in production: nothing sold would ever ship.
    CJ_DROPSHIPPING_SANDBOX: bool = False
    CJ_DROPSHIPPING_SANDBOX_SIMULATE_PAY_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/shopping/sandbox/simulatePay"
    )
    CJ_DROPSHIPPING_SANDBOX_UPDATE_STATUS_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/shopping/sandbox/updateStatus"
    )
    CJ_DROPSHIPPING_SANDBOX_UPDATE_TRACK_NUMBER_URL: str = "https://developers.cjdropshipping.com/api2.0/v1/shopping/sandbox/updateTrackNumber"
    CJ_DROPSHIPPING_ORDER_CREATE_TIMEOUT_SECONDS: float = 15.0

    # CJ Dropshipping checkout-time freight quotes
    CJ_DROPSHIPPING_FREIGHT_CALCULATE_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/logistic/freightCalculate"
    )
    CJ_DROPSHIPPING_FREIGHT_TIMEOUT_SECONDS: float = 15.0
    # Quotes are stable for minutes, not seconds; caching keeps checkout snappy
    # and stays well inside CJ's per-endpoint rate limits.
    CJ_DROPSHIPPING_FREIGHT_CACHE_TTL_SECONDS: int = 300
    CJ_DROPSHIPPING_FREIGHT_CACHE_MAX_ENTRIES: int = 512

    # CJ Dropshipping post-creation order tracking
    CJ_DROPSHIPPING_TRACK_INFO_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/logistic/trackInfo"
    )
    CJ_DROPSHIPPING_TRACKING_POLL_BATCH_SIZE: int = 50
    CJ_DROPSHIPPING_TRACKING_POLL_INTERVAL_MINUTES: int = 15
    # Stop polling an order that CJ never advanced; it needs human attention.
    CJ_DROPSHIPPING_TRACKING_MAX_AGE_DAYS: int = 90
    CJ_DROPSHIPPING_TRACKING_URL_TEMPLATE: str = (
        "https://cjpacket.com/track?trackNumber={tracking_number}"
    )

    # CJ Dropshipping shipping-address validation
    CJ_DROPSHIPPING_REJECT_PO_BOX_ADDRESSES: bool = True

    # CJ Dropshipping webhooks (stock pushes). CJ signs every push with the
    # account's openId (returned with the access token), so it is a secret.
    CJ_DROPSHIPPING_OPEN_ID: SecretStr | None = None

    # Stored email addresses are encrypted (infrastructure/utils/email_cipher.py):
    # EMAIL_ENCRYPTION_KEY encrypts, and EMAIL_ENCRYPTION_OLD_KEYS (comma
    # separated) still decrypt what earlier keys wrote, after a rotation.
    # EMAIL_LOOKUP_KEY keys the hash that finds a row by address. Each is 32
    # random bytes, base64, in this service's Vault path; dev.sh generates them
    # on `infra up`. Losing a key loses every address it encrypted: back it up.
    EMAIL_ENCRYPTION_KEY: SecretStr
    EMAIL_ENCRYPTION_OLD_KEYS: SecretStr | None = None
    # No column of this service is looked up by address.
    EMAIL_LOOKUP_KEY: SecretStr | None = None
    CJ_DROPSHIPPING_WEBHOOK_SET_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/webhook/set"
    )
    CJ_DROPSHIPPING_WEBHOOK_SUBSCRIBE_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/webhook/product/subscribe"
    )
    CJ_DROPSHIPPING_WEBHOOK_UNSUBSCRIBE_URL: str = (
        "https://developers.cjdropshipping.com/api2.0/v1/webhook/product/unsubscribe"
    )

    # --------------RABBITMQ-----------------------

    @property
    def RABBITMQ_BROKER_URL(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}"

    @property
    def FULL_PRODUCT_SERVICE_URL(self) -> str:
        return f"{self.PRODUCT_SERVICE_URL}{self.PRODUCT_SERVICE_URL_API_VERSION}"

    # ---------------SUPPLIER-SERVICE-------------------

    @property
    def SUPPLIER_SERVICE_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.SUPPLIER_SERVICE_DB}"

    @property
    def SUPPLIER_SERVICE_TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.SUPPLIER_SERVICE_TEST_DB}"

    @property
    def SUPPLIER_SERVICE_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.SUPPLIER_SERVICE_REDIS_DB}"

    # ------------CJDropshipping------------------------

    @property
    def CJ_DROPSHIPPING_AUTH_PAYLOAD(self) -> dict[str, str]:
        return {"apiKey": self.CJ_API_KEY}


class TestSettings(BaseSettings):
    API: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_test_settings() -> TestSettings:
    return TestSettings()

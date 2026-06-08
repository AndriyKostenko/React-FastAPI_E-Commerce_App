from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy.engine import URL
from pydantic import SecretStr, DirectoryPath
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.schemas.user_schemas import UserInfo, CurrentUserInfo
from shared.schemas.category_schema import CategorySchema
from shared.schemas.product_schemas import ProductBase, ProductSchema
from shared.schemas.review_schemas import ReviewSchema
from shared.schemas.notifications_schemas import NotificationInfo
from shared.enums.status_enums import OrderStatus, OrderDeliveryStatus

# Resolve the single shared .env that lives one level above this file (backend/.env)
_ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",   # ignore vars in .env that aren't declared on this model
    )

    # Application configuration
    APP_HOST: str
    FRONTEND_URL: str

    API_GATEWAY_SERVICE_APP_PORT: int
    USER_SERVICE_APP_PORT: int
    PRODUCT_SERVICE_APP_PORT: int
    NOTIFICATION_SERVICE_APP_PORT: int
    NOTIFICATION_CONSUMER_SERVICE_APP_PORT: int
    ORDER_SERVICE_APP_PORT: int
    PAYMENT_SERVICE_APP_PORT: int

    DEBUG_MODE: bool
    SECURE_COOKIES: bool # Set True in production (requires HTTPS)

    # PostgreSQL connection pool tuning — used by PoolSettingsCalculator
    PG_MAX_CONNECTIONS: int = 100       # must match postgresql.conf max_connections
    PG_RESERVED_CONNECTIONS: int = 5    # reserved for superuser / admin / monitoring
    PG_DB_SERVICES_COUNT: int = 5       # number of microservices sharing the same Postgres instance
    ALLOWED_HOSTS: list[str]

    # Service URLs
    API_GATEWAY_SERVICE_URL: str
    USER_SERVICE_URL: str
    PRODUCT_SERVICE_URL: str
    NOTIFICATION_SERVICE_URL: str
    NOTIFICATION_CONSUMER_SERVICE_URL: str
    ORDER_SERVICE_URL: str
    PAYMENT_SERVICE_URL: str

    API_GATEWAY_SERVICE_URL_API_VERSION: str
    USER_SERVICE_URL_API_VERSION: str
    PRODUCT_SERVICE_URL_API_VERSION: str
    NOTIFICATION_SERVICE_URL_API_VERSION: str
    NOTIFICATION_CONSUMER_SERVICE_URL_API_VERSION: str
    ORDER_SERVICE_URL_API_VERSION: str
    PAYMENT_SERVICE_URL_API_VERSION: str

    # Shared Database configuration
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    USER_SERVICE_DB: str
    PRODUCT_SERVICE_DB: str
    NOTIFICATION_SERVICE_DB: str
    ORDER_SERVICE_DB: str
    PAYMENT_SERVICE_DB: str

    USER_SERVICE_TEST_DB: str
    PRODUCT_SERVICE_TEST_DB: str
    NOTIFICATION_SERVICE_TEST_DB: str
    ORDER_SERVICE_TEST_DB: str
    PAYMENT_SERVICE_TEST_DB: str

    # pgAdmin
    PGADMIN_DEFAULT_EMAIL: str
    PGADMIN_DEFAULT_PASSWORD: str

    # RabbitMQ configuration
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    # Redis configuration
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    APIGATEWAY_SERVICE_REDIS_DB: int
    USER_SERVICE_REDIS_DB: int
    PRODUCT_SERVICE_REDIS_DB: int
    NOTIFICATION_SERVICE_REDIS_DB: int
    ORDER_SERVICE_REDIS_DB: int
    PAYMENT_SERVICE_REDIS_DB: int

    NOTIFICATION_SERVICE_REDIS_BACKEND_RESULT_DB: int

    USER_SERVICE_REDIS_PREFIX: str
    PRODUCT_SERVICE_REDIS_PREFIX: str
    APIGATEWAY_SERVICE_REDIS_PREFIX: str
    NOTIFICATION_SERVICE_REDIS_PREFIX: str
    ORDER_SERVICE_REDIS_PREFIX: str
    PAYMENT_SERVICE_REDIS_PREFIX: str

    IDEMPOTENCY_EVENT_SERVICE_HOURS: int

    # JWT configuration
    SECRET_KEY: str
    ALGORITHM: str
    TOKEN_TYPE: str
    TOKEN_URL: str
    TOKEN_TIME_DELTA_MINUTES: int
    REFRESH_TOKEN_TIME_DELTA_DAYS: int
    RESET_TOKEN_EXPIRY_MINUTES: int
    VERIFICATION_TOKEN_EXPIRY_MINUTES: int
    CRYPT_CONTEXT_SCHEME: str

    # Stripe
    STRIPE_TEST_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    # Email
    MAIL_USERNAME: str
    MAIL_PASSWORD: SecretStr
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool
    MAIL_DEBUG: bool
    MAIL_FROM: str
    MAIL_FROM_NAME: str
    USE_CREDENTIALS: bool
    TEMPLATES_DIR: DirectoryPath = Path(__file__).parent / "templates"
    VALIDATE_CERTS: bool

    # CORS
    CORS_ALLOWED_ORIGINS: list[str]
    CORS_ALLOW_CREDENTIALS: bool
    CORS_ALLOWED_METHODS: list[str]
    CORS_ALLOWED_HEADERS: list[str]

    # Google OAuth
    GOOGLE_CLIENT_ID: str

    #AdminJs
    ADMINJS_SERVICE_TOKEN: str

    # OpenRouter image generation
    OPENROUTER_API_KEY: str 
    OPENROUTER_BASE_URL: str 
    OPENROUTER_IMAGE_MODEL: str 
    OPENROUTER_IMAGE_SIZE: str = "0.5K"
    OPENROUTER_IMAGE_ASPECT_RATIO: str = "1:1"
    PRODUCT_IMAGE_GUEST_GENERATION_LIMIT: int = 3
    PRODUCT_IMAGE_REGISTERED_GENERATION_LIMIT: int = 10
    PRODUCT_IMAGE_GUEST_GENERATION_WINDOW_HOURS: int = 24
    GUEST_QUOTA_COOKIE: str = "guest_generation_id"

    # Other
    SECRET_ROLE: str
    POLLING_INTERVAL_FROM_DB: int | float
    CUSTOM_TSHIRT_BASE_PRICE: float


    #--------------RABBITMQ-----------------------

    @property
    def RABBITMQ_BROKER_URL(self):
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}"

    #--------------API-GATEWAY-----------------------

    @property
    def APIGATEWAY_SERVICE_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.APIGATEWAY_SERVICE_REDIS_DB}"

    @property
    def FULL_API_GATEWAY_SERVICE_URL(self) -> str:
        return f"{self.API_GATEWAY_SERVICE_URL}{self.API_GATEWAY_SERVICE_URL_API_VERSION}"

    #--------------USER-SERVICE---------------------

    @property
    def USER_SERVICE_DATABASE_URL(self) -> str | URL:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.USER_SERVICE_DB}"

    @property
    def USER_SERVICE_TEST_DATABASE_URL(self) -> str | URL:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.USER_SERVICE_TEST_DB}"

    @property
    def FULL_USER_SERVICE_URL(self) -> str | URL:
        return f"{self.USER_SERVICE_URL}{self.USER_SERVICE_URL_API_VERSION}"

    @property
    def USER_SERVICE_REDIS_URL(self) -> str | URL:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.USER_SERVICE_REDIS_DB}"

    #---------------PRODUCT-SERVICE-------------------

    @property
    def PRODUCT_SERVICE_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.PRODUCT_SERVICE_DB}"

    @property
    def PRODUCT_SERVICE_TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.PRODUCT_SERVICE_TEST_DB}"

    @property
    def FULL_PRODUCT_SERVICE_URL(self) -> str:
        return f"{self.PRODUCT_SERVICE_URL}{self.PRODUCT_SERVICE_URL_API_VERSION}"

    @property
    def PRODUCT_SERVICE_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.PRODUCT_SERVICE_REDIS_DB}"


    #---------------NOTIFICATION-SERVICE---------------

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
    def FULL_NOTIFICATION_SERVICE_URL(self) -> str:
        return f"{self.NOTIFICATION_SERVICE_URL}{self.NOTIFICATION_SERVICE_URL_API_VERSION}"

    @property
    def NOTIFICATION_SERVICE_REDIS_RESULT_BACKEND_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.NOTIFICATION_SERVICE_REDIS_BACKEND_RESULT_DB}"


    #-------------NOTIFICATION-CONSUMER-SERVICE----------------
    @property
    def FULL_NOTIFICATION_CONSUMER_SERVICE_URL(self) -> str:
        return f"{self.NOTIFICATION_CONSUMER_SERVICE_URL}{self.NOTIFICATION_CONSUMER_SERVICE_URL_API_VERSION}"



    #---------------ORDER-SERVICE-------------------

    @property
    def ORDER_SERVICE_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.ORDER_SERVICE_DB}"

    @property
    def ORDER_SERVICE_TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.ORDER_SERVICE_TEST_DB}"

    @property
    def ORDER_SERVICE_REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.ORDER_SERVICE_REDIS_DB}"

    @property
    def FULL_ORDER_SERVICE_URL(self) -> str:
        return f"{self.ORDER_SERVICE_URL}{self.ORDER_SERVICE_URL_API_VERSION}"


    #---------------PAYMENT-SERVICE-------------------

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
    def FULL_PAYMENT_SERVICE_URL(self) -> str:
        return f"{self.PAYMENT_SERVICE_URL}{self.PAYMENT_SERVICE_URL_API_VERSION}"

    @property
    def FULL_STRIPE_WEBHOOK_ENDPOINT(self) -> str:
        return f"https://{self.APP_HOST}{self.PAYMENT_SERVICE_URL_API_VERSION}/payments/webhook"


class TestSettings(BaseSettings):
    # ── Common ──────────────────────────────────────────────────────────────
    TEST_DATETIME: datetime = datetime(2024, 1, 1, 12, 0, 0)
    API: str = "/api/v1"

    # ── Auth / Token settings ────────────────────────────────────────────────
    CRYPT_CONTEXT_SCHEME: str = "bcrypt"
    SECRET_KEY: str = "test-secret-key-not-for-production"
    ALGORITHM: str = "HS256"
    REFRESH_TOKEN_TIME_DELTA_DAYS: int = 7

    # ── User ────────────────────────────────────────────────────────────────
    TEST_USER_ID: UUID = uuid4()
    TEST_ADMIN_ID: UUID = uuid4()
    TEST_USER_ROLE: str = "user"
    TEST_ADMIN_ROLE: str = "shiba_inu"
    TEST_NAME: str = "Test User"
    TEST_EMAIL: str = "test@example.com"
    TEST_ADMIN_EMAIL: str = "admin@example.com"
    TEST_PHONE_NUMBER: str = "4372998642"
    TEST_PASSWORD: str = "Password123!"
    TEST_HASHED_PW: str = "$2b$12$fakehashfortesting000000000000000000"

    # ── Product ─────────────────────────────────────────────────────────────
    TEST_PRODUCT_ID: UUID = uuid4()
    TEST_CATEGORY_ID: UUID = uuid4()
    TEST_REVIEW_ID: UUID = uuid4()
    TEST_IMAGE_ID: UUID = uuid4()

    # ── Order ────────────────────────────────────────────────────────────────
    TEST_ORDER_ID: UUID = uuid4()
    TEST_ORDER_ITEM_ID: UUID = uuid4()
    TEST_ORDER_ADDRESS_ID: UUID = uuid4()
    TEST_PAYMENT_INTENT_ID: str = "pi_test_order_abc123"
    TEST_AMOUNT: float = 99.99
    TEST_CURRENCY: str = "usd"

    # ── Payment ──────────────────────────────────────────────────────────────
    TEST_PAYMENT_ID: UUID = uuid4()
    TEST_STRIPE_INTENT_ID: str = "pi_test_abc123"
    TEST_CLIENT_SECRET: str = "pi_test_abc123_secret_xyz"
    TEST_AMOUNT_CENTS: int = 9999  # payment amount in cents

    # ── Notification ─────────────────────────────────────────────────────────
    TEST_NOTIFICATION_ID: UUID = uuid4()
    TEST_NOTIFICATION_TYPE: str = "user.registered"
    TEST_MESSAGE: str = "Welcome! Please verify your email address."
    TEST_EVENT_ID: str = str(uuid4())

    # ── User schema objects ──────────────────────────────────────────────────
    USER_INFO: UserInfo = UserInfo(
        id=TEST_USER_ID,
        name=TEST_NAME,
        email=TEST_EMAIL,
        role=TEST_USER_ROLE,
        phone_number=TEST_PHONE_NUMBER,
        image=None,
        date_created=TEST_DATETIME,
        date_updated=TEST_DATETIME,
        is_verified=True,
        is_active=True,
    )

    CURRENT_USER: CurrentUserInfo = CurrentUserInfo(
        email=TEST_EMAIL,
        id=TEST_USER_ID,
        role=TEST_USER_ROLE,
    )

    ADMIN_USER: CurrentUserInfo = CurrentUserInfo(
        email=TEST_ADMIN_EMAIL,
        id=TEST_ADMIN_ID,
        role=TEST_ADMIN_ROLE,
    )

    # ── Product schema objects ───────────────────────────────────────────────
    MOCK_CATEGORY_SCHEMA: CategorySchema = CategorySchema(
        id=TEST_CATEGORY_ID,
        name="electronics",
        image_url=None,
        date_created=TEST_DATETIME,
        date_updated=None,
    )

    MOCK_PRODUCT_BASE: ProductBase = ProductBase(
        id=TEST_PRODUCT_ID,
        name="test laptop",
        description="A high-quality test laptop for testing purposes",
        category_id=TEST_CATEGORY_ID,
        brand="testbrand",
        quantity=10,
        price=Decimal("999.99"),
        in_stock=True,
        date_created=TEST_DATETIME,
        date_updated=None,
    )

    MOCK_PRODUCT_SCHEMA: ProductSchema = ProductSchema(
        id=TEST_PRODUCT_ID,
        name="test laptop",
        description="A high-quality test laptop for testing purposes",
        category_id=TEST_CATEGORY_ID,
        brand="testbrand",
        quantity=10,
        price=Decimal("999.99"),
        in_stock=True,
        date_created=TEST_DATETIME,
        date_updated=None,
        reviews=[],
        category=MOCK_CATEGORY_SCHEMA,
        images=[],
    )

    MOCK_REVIEW_SCHEMA: ReviewSchema = ReviewSchema(
        id=TEST_REVIEW_ID,
        product_id=TEST_PRODUCT_ID,
        user_id=TEST_USER_ID,
        comment="Great product!",
        rating=4.5,
        date_created=TEST_DATETIME,
        date_updated=None,
    )

    # ── Notification schema objects ──────────────────────────────────────────
    MOCK_NOTIFICATION_INFO: NotificationInfo = NotificationInfo(
        id=TEST_NOTIFICATION_ID,
        user_id=TEST_USER_ID,
        message=TEST_MESSAGE,
        notification_type=TEST_NOTIFICATION_TYPE,
        is_read=False,
        date_created=TEST_DATETIME,
        date_updated=None,
    )

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

    MOCK_ORDER_RESULT: dict = {
        "id": str(TEST_ORDER_ID),
        "user_id": str(TEST_USER_ID),
        "user_email": TEST_EMAIL,
        "amount": TEST_AMOUNT,
        "currency": TEST_CURRENCY,
        "status": OrderStatus.PENDING,
        "delivery_status": OrderDeliveryStatus.PENDING,
        "payment_intent_id": TEST_PAYMENT_INTENT_ID,
        "address_id": str(TEST_ORDER_ADDRESS_ID),
        "date_created": TEST_DATETIME.isoformat(),
        "date_updated": None,
    }

    MOCK_PAYMENT_INTENT_RESULT: dict = {
        "client_secret": TEST_CLIENT_SECRET,
        "stripe_payment_intent_id": TEST_STRIPE_INTENT_ID,
        "payment_id": str(TEST_PAYMENT_ID),
        "order_id": str(TEST_ORDER_ID),
    }

    MOCK_UPSTREAM_RESPONSE_BODY: dict = {"status": "ok", "data": "upstream_result"}

    # ── Auth request payload helpers ─────────────────────────────────────────
    REGISTER_PAYLOAD: dict = {"name": "Test User", "email": "test@example.com", "password": "secret123"}
    LOGIN_DATA: dict = {"username": "test@example.com", "password": "secret123"}






@lru_cache()
def get_settings():
    return Settings()

@lru_cache
def get_test_settings():
    return TestSettings()

from functools import lru_cache
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy.engine import URL
from pydantic import SecretStr, DirectoryPath
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.schemas.user_schemas import UserInfo, CurrentUserInfo

# Resolve the single shared .env that lives one level above this file (backend/.env)
_ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",   # ignore vars in .env that aren't declared on this model
    )

    # Application configuration
    APP_HOST: str

    API_GATEWAY_SERVICE_APP_PORT: int
    USER_SERVICE_APP_PORT: int
    PRODUCT_SERVICE_APP_PORT: int
    NOTIFICATION_SERVICE_APP_PORT: int
    NOTIFICATION_CONSUMER_SERVICE_APP_PORT: int
    ORDER_SERVICE_APP_PORT: int
    PAYMENT_SERVICE_APP_PORT: int

    DEBUG_MODE: bool
    SECURE_COOKIES: bool # Set True in production (requires HTTPS)
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

    #AdminJs
    ADMINJS_SERVICE_TOKEN: str

    # Other
    SECRET_ROLE: str
    POLLING_INTERVAL_FROM_DB: int | float


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
    TEST_USER_ID: UUID = uuid4()
    TEST_EMAIL: str = "test@example.com"
    TEST_NAME: str = "Test User"
    TEST_HASHED_PW: str = "$2b$12$fakehashfortesting000000000000000000"
    TEST_DATETIME: datetime = datetime(2024, 1, 1, 12, 0, 0)
    TEST_USER_ROLE: str = "user"
    TEST_PHONE_NUMBER: str = "4372998642"
    TEST_PASSWORD: str  = "Password123!"
 
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
        role=TEST_USER_ROLE
    )

    CRYPT_CONTEXT_SCHEME: str = "bcrypt"
    SECRET_KEY: str = "test-secret-key-not-for-production"
    ALGORITHM: str = "HS256"
    REFRESH_TOKEN_TIME_DELTA_DAYS: int = 7

    API: str = "/api/v1"

    REGISTER_PAYLOAD: dict[str, str] = {"name": "Test User", "email": "test@example.com", "password": "secret123"}
    LOGIN_DATA: dict[str, str] = {"username": "test@example.com", "password": "secret123"}  # OAuth2 form fields






@lru_cache()
def get_settings():
    return Settings()

@lru_cache
def get_test_settings():
    return TestSettings()

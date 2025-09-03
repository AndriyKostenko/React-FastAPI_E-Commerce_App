from functools import lru_cache
from pathlib import Path
from typing import List


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    
    
    # Application configuration
    APP_HOST: str
    
    API_GATEWAY_SERVICE_APP_PORT: int
    USER_SERVICE_APP_PORT: int
    PRODUCT_SERVICE_APP_PORT: int
    NOTIFICATION_SERVICE_APP_PORT: int
    NOTIFICATION_CONSUMER_SERVICE_APP_PORT: int
    
    DEBUG_MODE: bool
    ALLOWED_HOSTS: List[str]

    # Service URLs
    API_GATEWAY_SERVICE_URL: str
    USER_SERVICE_URL: str
    PRODUCT_SERVICE_URL: str
    NOTIFICATION_SERVICE_URL: str
    NOTIFICATION_CONSUMER_SERVICE_URL: str

    API_GATEWAY_SERVICE_URL_API_VERSION: str
    USER_SERVICE_URL_API_VERSION: str
    PRODUCT_SERVICE_URL_API_VERSION: str
    NOTIFICATION_SERVICE_URL_API_VERSION: str
    NOTIFICATION_CONSUMER_SERVICE_URL_API_VERSION: str

    # Shared Database configuration
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    USER_SERVICE_DB: str
    USER_SERVICE_TEST_DB: str
    PRODUCT_SERVICE_DB: str
    PRODUCT_SERVICE_TEST_DB: str
    NOTIFICATION_SERVICE_DB: str
    NOTIFICATION_SERVICE_TEST_DB: str

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
    
    USER_SERVICE_REDIS_PREFIX: str
    PRODUCT_SERVICE_REDIS_PREFIX: str
    APIGATEWAY_SERVICE_REDIS_PREFIX: str
    NOTIFICATION_SERVICE_REDIS_PREFIX: str

    # JWT configuration
    SECRET_KEY: str
    ALGORITHM: str
    TOKEN_TYPE: str
    TOKEN_URL: str
    TIME_DELTA_MINUTES: int
    RESET_TOKEN_EXPIRY_MINUTES: int
    VERIFICATION_TOKEN_EXPIRY_MINUTES: int
    CRYPT_CONTEXT_SCHEME: str

    # Stripe
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    # Email
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool
    MAIL_DEBUG: bool
    MAIL_FROM: str
    MAIL_FROM_NAME: str
    USE_CREDENTIALS: bool
    TEMPLATES_DIR: str 
    VALIDATE_CERTS: bool

    # CORS
    CORS_ALLOWED_ORIGINS: List[str]
    CORS_ALLOW_CREDENTIALS: bool
    CORS_ALLOWED_METHODS: List[str]
    CORS_ALLOWED_HEADERS: List[str]

    # Other
    SECRET_ROLE: str


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
    def USER_SERVICE_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.USER_SERVICE_DB}"

    @property
    def USER_SERVICE_TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.USER_SERVICE_TEST_DB}"

    @property
    def FULL_USER_SERVICE_URL(self) -> str:
        return f"{self.USER_SERVICE_URL}{self.USER_SERVICE_URL_API_VERSION}"
    
    @property
    def USER_SERVICE_REDIS_URL(self) -> str:
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


    #-------------NOTIFICATION-CONSUMER-SERVICE----------------
    @property
    def FULL_NOTIFICATION_CONSUMER_SERVICE_URL(self) -> str:
        return f"{self.NOTIFICATION_CONSUMER_SERVICE_URL}{self.NOTIFICATION_CONSUMER_SERVICE_URL_API_VERSION}"



    @classmethod
    def customise_sources(cls, settings_cls, init_settings, env_settings, file_secret_settings):
        """
        Customise sources to support shared and service-specific .env 
        """
        root_env = Path(__file__).resolve().parents[1] / ".env"
        local_env = Path(__file__).resolve().parent / ".env"
        return (
            init_settings,
            env_settings,
            cls.env_file_settings_source(root_env),   # shared # type: ignore
            cls.env_file_settings_source(local_env),  # service-specific # type: ignore
            file_secret_settings,
        )
        

@lru_cache()
def get_settings():
    return Settings() # type: ignore
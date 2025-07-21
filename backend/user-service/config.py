from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    USER_SERVICE_DB: str
    USER_SERVICE_TEST_DB: str
    SECRET_KEY: str
    ALGORITHM: str 
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    TIME_DELTA_MINUTES: int 
    TOKEN_TYPE: str 
    TOKEN_URL: str 
    CRYPT_CONTEXT_SCHEME: str 
    RESET_TOKEN_EXPIRY_MINUTES: int 
    VERIFICATION_TOKEN_EXPIRY_MINUTES: int 
    APP_HOST: str 
    APP_PORT: int 
    MAIL_USERNAME: str
    MAIL_PASSWORD: str 
    MAIL_FROM: str 
    MAIL_PORT: int 
    MAIL_SERVER: str 
    MAIL_FROM_NAME: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool
    MAIL_DEBUG: bool
    USE_CREDENTIALS: bool 
    TEMPLATES_DIR: str 
    VALIDATE_CERTS: bool 
    SECRET_ROLE: str 
    REDIS_HOST: str 
    REDIS_PORT: int
    REDIS_PASSWORD: str
    USER_SERVICE_REDIS_PREFIX: str
    USER_SERVICE_REDIS_DB: int
    DEBUG_MODE: bool 
    CORS_ALLOWED_ORIGINS: list[str] 
    CORS_ALLOW_CREDENTIALS: bool 
    CORS_ALLOWED_METHODS: list[str] 
    CORS_ALLOWED_HEADERS: list[str] 
    ALLOWED_HOSTS: list[str]
    CRYPT_CONTEXT_SCHEME: str
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.USER_SERVICE_DB}"

    @property
    def TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.USER_SERVICE_TEST_DB}"

    @property
    def ALEMBIC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.USER_SERVICE_REDIS_DB}"

    
    # ovveriding the adding an option to get common .env settings
    @classmethod
    def customise_sources(cls, settings_cls, init_settings, env_settings, file_secret_settings):
        root_env = Path(__file__).resolve().parents[1] / ".env"
        local_env = Path(__file__).resolve().parent / ".env"
        return (
            init_settings,
            env_settings,
            cls.env_file_settings_source(root_env),   # shared
            cls.env_file_settings_source(local_env),  # service-specific
            file_secret_settings,
        )
        
        

@lru_cache()
def get_settings():
    return Settings()






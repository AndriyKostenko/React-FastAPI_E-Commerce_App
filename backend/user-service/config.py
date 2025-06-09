from functools import lru_cache
import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BASE_DIR: Path = Path(__file__).resolve().parent.parent  # This points to backend/
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    TEST_DATABASE_URL: str  = os.getenv("TEST_DATABASE_URL")
    SECRET_KEY: str= os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM")
    ALEMBIC_DATABASE_URL: str = os.getenv("ALEMBIC_DATABASE_URL")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET")
    TIME_DELTA_MINUTES: int = os.getenv("TIME_DELTA_MINUTES")
    TOKEN_TYPE: str = os.getenv("TOKEN_TYPE")
    TOKEN_URL: str = os.getenv("TOKEN_URL")
    CRYPT_CONTEXT_SCHEME: str = os.getenv("CRYPT_CONTEXT_SCHEME")
    RESET_TOKEN_EXPIRY_MINUTES: int = os.getenv("RESET_TOKEN_EXPIRY_MINUTES")
    VERIFICATION_TOKEN_EXPIRY_MINUTES: int = os.getenv("VERIFICATION_TOKEN_EXPIRY_MINUTES")
    APP_HOST: str = os.getenv("APP_HOST")
    APP_PORT: int = os.getenv("APP_PORT")
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD")
    MAIL_FROM: str = os.getenv("MAIL_FROM")
    MAIL_PORT: int = os.getenv("MAIL_PORT")
    MAIL_SERVER: str = os.getenv("MAIL_SERVER")
    MAIL_FROM_NAME: str = os.getenv("MAIL_FROM_NAME")
    MAIL_STARTTLS: bool = os.getenv("MAIL_START_TLS")
    MAIL_SSL_TLS: bool = os.getenv("MAIL_SSL_TLS")
    MAIL_DEBUG: bool = os.getenv("MAIL_DEBUG")
    USE_CREDENTIALS: bool = os.getenv("USE_CREDENTIALS")
    TEMPLATES_DIR: Path = BASE_DIR / os.getenv("TEMPLATES_DIR", "templates")
    VALIDATE_CERTS: bool = os.getenv("VALIDATE_CERTS")
    SECRET_ROLE: str = os.getenv("SECRET_ROLE")
    REDIS_ENDPOINT: str = os.getenv("REDIS_ENDPOINT")
    REDIS_PORT: int = os.getenv("REDIS_PORT")
    REDIS_DB: int = os.getenv("REDIS_DB")
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE")
    CORS_ALLOWED_ORIGINS: list[str] = os.getenv("CORS_ALLOWED_ORIGINS")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS")
    CORS_ALLOWED_METHODS: list[str] = os.getenv("CORS_ALLOWED_METHODS")
    CORS_ALLOWED_HEADERS: list[str] = os.getenv("CORS_ALLOWED_HEADERS")
    
    class Config:
        env_file = ".env"
 

@lru_cache()
def get_settings():
    return Settings()






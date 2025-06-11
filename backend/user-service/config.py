from functools import lru_cache
import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str 
    TEST_DATABASE_URL: str  
    SECRET_KEY: str
    ALGORITHM: str 
    ALEMBIC_DATABASE_URL: str 
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
    TEMPLATES_DIR: str = "templates"
    VALIDATE_CERTS: bool 
    SECRET_ROLE: str 
    REDIS_ENDPOINT: str 
    REDIS_PORT: int
    REDIS_DB: int 
    DEBUG_MODE: bool 
    CORS_ALLOWED_ORIGINS: list[str] 
    CORS_ALLOW_CREDENTIALS: bool 
    CORS_ALLOWED_METHODS: list[str] 
    CORS_ALLOWED_HEADERS: list[str] 
    ALLOWED_HOSTS: list[str]
    CRYPT_CONTEXT_SCHEME: str
    
    class Config:
        env_file = ".env"
 

@lru_cache()
def get_settings():
    return Settings()






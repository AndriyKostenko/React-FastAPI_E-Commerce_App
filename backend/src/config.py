from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
from pathlib import Path

env_path = Path(".") / ".env"



# Load environment variables from .env file
load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    BASE_DIR: Path = Path(__file__).resolve().parent.parent  # This points to backend/
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")
    TEST_DATABASE_URL: str | None  = os.getenv("TEST_DATABASE_URL")
    SECRET_KEY: str | None = os.getenv("SECRET_KEY")
    ALGORITHM: str | None = os.getenv("ALGORITHM")
    ALEMBIC_DATABASE_URL: str | None = os.getenv("ALEMBIC_DATABASE_URL")
    STRIPE_SECRET_KEY: str | None = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: str | None = os.getenv("STRIPE_WEBHOOK_SECRET")
    TIME_DELTA_MINUTES: int = int(os.getenv("TIME_DELTA_MINUTES"))
    TOKEN_TYPE: str | None = os.getenv("TOKEN_TYPE")
    TOKEN_URL: str = os.getenv("TOKEN_URL")
    CRYPT_CONTEXT_SCHEME: str | None = os.getenv("CRYPT_CONTEXT_SCHEME")
    RESET_TOKEN_EXPIRY_MINUTES: int | None = int(os.getenv("RESET_TOKEN_EXPIRY_MINUTES"))
    VERIFICATION_TOKEN_EXPIRY_MINUTES: int | None = int(os.getenv("VERIFICATION_TOKEN_EXPIRY_MINUTES"))
    APP_HOST: str | None = os.getenv("APP_HOST")
    APP_PORT: int | None = int(os.getenv("APP_PORT"))
    MAIL_USERNAME: str | None = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD: str | None = os.getenv("MAIL_PASSWORD")
    MAIL_FROM: str | None = os.getenv("MAIL_FROM")
    MAIL_PORT: int | None = int(os.getenv("MAIL_PORT"))
    MAIL_SERVER: str | None = os.getenv("MAIL_SERVER")
    MAIL_FROM_NAME: str | None = os.getenv("MAIL_FROM_NAME")
    MAIL_STARTTLS: bool | None = os.getenv("MAIL_START_TLS")
    MAIL_SSL_TLS: bool | None = os.getenv("MAIL_SSL_TLS")
    MAIL_DEBUG: bool | None = os.getenv("MAIL_DEBUG")
    USE_CREDENTIALS: bool | None = os.getenv("USE_CREDENTIALS")
    TEMPLATES_DIR: Path = BASE_DIR / os.getenv("TEMPLATES_DIR", "templates")
    VALIDATE_CERTS: bool | None = os.getenv("VALIDATE_CERTS")
    
    class Config:
        env_file = env_path
 


settings = Settings()




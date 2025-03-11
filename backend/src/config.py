from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    TEST_DATABASE_URL: str = os.getenv("TEST_DATABASE_URL")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM")
    ALEMBIC_DATABASE_URL: str = os.getenv("ALEMBIC_DATABASE_URL")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET")
    TIME_DELTA_MINUTES: int = int(os.getenv("TIME_DELTA_MINUTES"))
    TOKEN_TYPE: str = os.getenv("TOKEN_TYPE")
    TOKEN_URL: str = os.getenv("TOKEN_URL")
    CRYPT_CONTEXT_SCHEME: str = os.getenv("CRYPT_CONTEXT_SCHEME")


settings = Settings()

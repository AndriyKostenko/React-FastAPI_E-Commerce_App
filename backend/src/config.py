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


settings = Settings()

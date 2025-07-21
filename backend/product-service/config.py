from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    PRODUCT_SERVICE_DB: str
    PRODUCT_SERVICE_TEST_DB: str
    APP_HOST: str 
    APP_PORT: int 
    USE_CREDENTIALS: bool 
    TEMPLATES_DIR: str 
    SECRET_ROLE: str 
    REDIS_HOST: str 
    REDIS_PORT: int
    PRODUCT_SERVICE_REDIS_DB: int
    PRODUCT_SERVICE_REDIS_PREFIX: str 
    DEBUG_MODE: bool 
    CORS_ALLOWED_ORIGINS: list[str] 
    CORS_ALLOW_CREDENTIALS: bool 
    CORS_ALLOWED_METHODS: list[str] 
    CORS_ALLOWED_HEADERS: list[str] 
    ALLOWED_HOSTS: list[str]
    USE_CREDENTIALS: bool
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.PRODUCT_SERVICE_DB}"

    @property
    def TEST_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.PRODUCT_SERVICE_TEST_DB}"

    @property
    def ALEMBIC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.PRODUCT_SERVICE_REDIS_DB}"   
    
    # ovveriding by adding an option to get a common .env settings
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






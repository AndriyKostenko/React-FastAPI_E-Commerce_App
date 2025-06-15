from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str 
    TEST_DATABASE_URL: str  
    ALEMBIC_DATABASE_URL: str 
    APP_HOST: str 
    APP_PORT: int 
    USE_CREDENTIALS: bool 
    TEMPLATES_DIR: str = "templates"
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
    
    class Config:
        env_file = ".env"
 

@lru_cache()
def get_settings():
    return Settings()






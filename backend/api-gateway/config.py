from functools import lru_cache

from pydantic_settings import BaseSettings
from redis import Redis


class Settings(BaseSettings):
    APP_PORT: int
    APP_HOST: str
    USER_SERVICE_URL: str
    PRODUCT_SERVICE_URL: str
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    
        
        
@lru_cache()
def get_settings():
    return Settings()






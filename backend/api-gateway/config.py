from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    USER_SERVICE_URL: str
    PRODUCT_SERVICE_URL: str
        
        
@lru_cache()
def get_settings():
    return Settings()






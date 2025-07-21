from functools import lru_cache

from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    APP_PORT: int
    APP_HOST: str
    USER_SERVICE_URL: str
    PRODUCT_SERVICE_URL: str
    REDIS_HOST: str
    REDIS_PORT: int
    APIGATEWAY_SERVICE_REDIS_PREFIX: str
    APIGATEWAY_SERVICE_REDIS_DB: int
    REDIS_PASSWORD: str

    
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.APIGATEWAY_SERVICE_REDIS_DB}"
    
        
        
@lru_cache()
def get_settings():
    return Settings()






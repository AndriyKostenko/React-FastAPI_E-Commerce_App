from pydantic import BaseModel, BaseSettings


class ServiceConfig(BaseModel):
    name: str
    instances: list[str]
    health_check_path: str = "/health"
    timeout: int = 30
    retries: int = 3

class GatewayConfig(BaseModel):
    services: dict[str, ServiceConfig]
    jwt_secret: str = "your-jwt-secret-key"
    jwt_algorithm: str = "HS256"
    rate_limit_per_minute: int = 100
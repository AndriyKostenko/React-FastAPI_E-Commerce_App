from uuid import UUID
from pydantic import BaseModel, EmailStr


class ServiceConfig(BaseModel):
    name: str
    instances: list[str]
    health_check_path: str = "/health"



class GatewayConfig(BaseModel):
    services: dict[str, ServiceConfig]
    jwt_secret: str = "your-jwt-secret-key"
    jwt_algorithm: str = "HS256"
    rate_limit_per_minute: int = 100
    
    
class CurrentUserInfo(BaseModel):
    email: EmailStr
    id: UUID
    role: str | None
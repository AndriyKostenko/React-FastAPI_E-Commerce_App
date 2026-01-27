from pydantic import BaseModel


class ServiceConfig(BaseModel):
    name: str
    instances: list[str]
    health_check_path: str
    api_version: str


class GatewayConfig(BaseModel):
    services: dict[str, ServiceConfig]

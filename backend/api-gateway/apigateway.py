from fastapi import HTTPException
from fastapi.responses import JSONResponse
import httpx
from circuitbreaker import circuit

from shared.shared_instances import settings, logger
from schemas.schemas import GatewayConfig, ServiceConfig


class ApiGateway:
    """
    A class representing the API Gateway that forwards requests to microservices.
    """  
    
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.config = GatewayConfig(
            services={
                "user-service": ServiceConfig(
                    name="user-service",
                    instances=[self.settings.FULL_USER_SERVICE_URL],
                    health_check_path="/health"
                    ),
                "product-service": ServiceConfig(
                    name="product-service",
                    instances=[self.settings.FULL_PRODUCT_SERVICE_URL],
                    health_check_path="/health"
                    )
                
            }
        )

    @circuit(failure_threshold=5, recovery_timeout=30)
    async def forward_request(self, service_key: str, method: str, path: str, body=None, headers=None, current_user=None) -> JSONResponse:
        
        self.logger.debug(f"Available services: {list(self.config.services.keys())}")
        self.logger.debug(f"Requested service key: {service_key}")
        
        if service_key not in self.config.services:
            self.logger.error(f"Service key: {service_key} is not recognized.")
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Get the actual service configuration
        service_config = self.config.services[service_key]
        
        # Use the first instance URL (you can add load balancing logic later)
        service_url = service_config.instances[0]
        
        # Build the full URL robustly

        url = f"{service_url}/{path}"
        
        self.logger.info(f"Forwarding request to: {url} with method: {method} and body: {body}")
        
        # Add user context if authenticated
        if current_user:
            if headers is None:
                headers = {}
            headers["X-User-ID"] = str(current_user.get("user_id", ""))
            headers["X-User-Role"] = current_user.get("user_role", "user")
        
        # perform the request using httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method, 
                    url=url, 
                    content=body,  # Use content instead of body
                    headers=headers
                )
            
                content = response.json() if response.content else ''
                
                self.logger.debug(f"Response in api-gateway from {service_key}, content:{content}, status code: {response.status_code}")
                
                return JSONResponse(
                    content=content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
                
            except httpx.HTTPStatusError as e:
                self.logger.error(f"HTTP error occurred: {e}")
                raise HTTPException(status_code=e.response.status_code, detail=str(e))
            except httpx.RequestError as e:
                self.logger.error(f"Request error occurred: {e}")
                raise HTTPException(status_code=500, detail="Internal Server Error")
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                raise HTTPException(status_code=500, detail="Internal Server Error")


api_gateway_manager = ApiGateway(settings=settings, logger=logger)
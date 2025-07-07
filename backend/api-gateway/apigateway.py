from urllib.parse import urljoin

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx
from circuitbreaker import circuit

from config import get_settings
from utils.logger_config import setup_logger


MICROSERVICES = {
    "user_service": "http://user-service:8000",
    "product_service": "http://product-service:8001",
}


class ApiGateway:
    """A class representing the API Gateway that forwards requests to microservices."""  
    def __init__(self):
        self.settings = get_settings()
        self.logger = setup_logger(__name__)

    @circuit(failure_threshold=5, recovery_timeout=30)
    async def forward_request(self, service_url: str, method: str, path: str, body=None, headers=None):
    # Remove trailing slash from service_url and leading slash from path
        service_url = service_url.rstrip('/')
        
        if service_url not in MICROSERVICES.values():
            self.logger.error(f"Service URL: {service_url} is not recognized.")
            raise HTTPException(status_code=404, detail="Service not found")
        
        
        url = urljoin(service_url, path.lstrip('/'))
        
        self.logger.info(f"Forwarding request to: {url} with method: {method} and body: {body}")
        
        async with httpx.AsyncClient() as client:
            await client.request(method=method, 
                                        url=url, 
                                        body=body, 
                                        headers=headers)



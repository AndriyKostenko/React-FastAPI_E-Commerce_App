from email import header
from urllib.parse import urljoin
from fastapi import HTTPException, Request
import json

from httpx import AsyncClient, HTTPStatusError, RequestError #type: ignore
from circuitbreaker import circuit #type: ignore
from shared.customized_json_response import JSONResponse

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
                    ),
                "notification-service": ServiceConfig(
                    name="notification-service",
                    instances=[self.settings.FULL_NOTIFICATION_SERVICE_URL],
                    health_check_path="/health"
                )
                
            }
        )


    async def _detect_and_prepare_body(self, request: Request, path: str):
        """
        Detects the content type of the body and prepares it for forwarding.
        Returns: (prepared_body, content_type_header)
        """
        content_type = request.headers.get("content-type", "").lower()
        
        # Handling different content types
        
        if "application/json" in content_type:
            body_data = await request.json()
            if path == "/login":
                raise HTTPException(status_code=500, detail="The /login endpoint data must be sent via application/x-www-form-urlencoded ")
            return body_data, "application/json"
            
        elif "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            # Convert FormData to dict
            body_dict = dict()
            for key in form_data.keys():
                body_dict[key] = form_data[key]
            
            # For login, ensure username field exists as OAuth2 expects it (assuming u are passing email and password)
            if path == "/login":
                form_data = {
                    "username": form_data.get("email") or form_data.get("username"),
                    "password": form_data.get("password")
                }
                return form_data, "application/x-www-form-urlencoded"
            
            return body_dict, "application/x-www-form-urlencoded"
            
        elif "multipart/form-data" in content_type:
            form_data = await request.form()
            # For multipart, we need to handle files differently
            return form_data, "multipart/form-data"
            
        else:
            # Raw body for other content types
            raw_body = await request.body()
            if len(raw_body) == 0:
                return None, None
            return raw_body, content_type


    def _prepare_headers(self, request_headers, new_content_type=None):
        """
        Prepare headers for forwarding, removing problematic ones and adding new content-type if needed
        """
        filtered_headers = {}
        if request_headers:
            for key, value in dict(request_headers).items():
                if key.lower() not in ["host", "content-length", "transfer-encoding", "connection", "content-type"]:
                    filtered_headers[key] = value
        
        if new_content_type:
            filtered_headers["Content-Type"] = new_content_type
            
        return filtered_headers

    @circuit(failure_threshold=5, recovery_timeout=30)
    async def forward_request(self, request: Request, service_key: str, path: str) -> JSONResponse:

        if service_key not in self.config.services:
            self.logger.error(f"Service key: {service_key} is not recognized.")
            raise HTTPException(status_code=404, detail="Service not found")
        
        service_config = self.config.services[service_key]     
        service_url = service_config.instances[0]
        url = urljoin(service_url.rstrip('/') + '/', path.lstrip('/'))
        
        # detecting and preparing body
        prepared_body, content_type = await self._detect_and_prepare_body(request, path)
        
        # preparing headers
        headers = self._prepare_headers(request_headers=request.headers, new_content_type=content_type)

        self.logger.info(f"Forwarding request to: {url} with method: {request.method}")
        self.logger.debug(f"Body type: {type(prepared_body)}, Content-Type: {content_type}")
        self.logger.debug(f"Headers: {headers}")
        
        # perform the request using httpx
        async with AsyncClient() as client:
            try:
                if prepared_body is None:
                    # No body
                    response = await client.request(
                        method=request.method,
                        url=url,
                        headers=headers
                    )
                elif content_type == "application/json":
                    # JSON body
                    response = await client.request(
                        method=request.method,
                        url=url,
                        json=prepared_body,
                        headers={k: v for k, v in headers.items() if k.lower() != "content-type"}  # httpx sets content-type for json
                    )
                elif content_type == "application/x-www-form-urlencoded":
                    # Form data
                    response = await client.request(
                        method=request.method,
                        url=url,
                        data=prepared_body,
                        headers={k: v for k, v in headers.items() if k.lower() != "content-type"}  # httpx sets content-type for data
                    )
                elif content_type == "multipart/form-data":
                    # Multipart form data (files)
                    response = await client.request(
                        method=request.method,
                        url=url,
                        files=prepared_body,
                        headers={k: v for k, v in headers.items() if k.lower() != "content-type"}  # httpx sets content-type for files
                    )
                else:
                    # Raw content
                    response = await client.request(
                        method=request.method,
                        url=url,
                        content=prepared_body,
                        headers=headers
                    )
                    
                # Parse response
                try:
                    content = response.json()
                except json.JSONDecodeError:
                    # If response is not JSON, return text
                    content = {"message": response.text, "status_code": response.status_code}
                
                self.logger.debug(f"Response from {service_key}: status={response.status_code}")
                
                return JSONResponse(
                    content=content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
                
            except HTTPStatusError as e:
                self.logger.error(f"HTTP error occurred: {e}")
                raise HTTPException(status_code=e.response.status_code, detail=str(e))
            except RequestError as e:
                self.logger.error(f"Request error occurred: {e}")
                raise HTTPException(status_code=500, detail="Internal Server Error")
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                raise HTTPException(status_code=500, detail="Internal Server Error")


api_gateway_manager = ApiGateway(settings=settings, logger=logger)
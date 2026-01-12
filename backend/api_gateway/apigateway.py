import random
from urllib.parse import urljoin, urlparse, urlunparse
import orjson

from fastapi import HTTPException, Request
from httpx import AsyncClient, HTTPStatusError, RequestError #type: ignore
from circuitbreaker import circuit #type: ignore
from shared.customized_json_response import JSONResponse

from shared.shared_instances import settings, logger
from schemas.schemas import GatewayConfig, ServiceConfig


class UrlManager:
    
    def __init__(self, config: ServiceConfig, logger):
        self.config = config
        self.logger = logger
        
    
    def extract_service_path(self, path: str, service_name: str) -> str:
        """
        Extract the path that should be forwarded to the given microservice.
        
        Example:
        - Incoming path: http://127.0.0.1:8000/api/v1/login
        - Service: user-service
        - Service base: http://user-service:8001
        - Returns: /login
        """
        parsed = urlparse(path)
        api_version = self.config.services[service_name].api_version  # e.g. "/api/v1"
        
        # Normalize both paths to avoid double slashes or mismatches
        path_only = parsed.path.strip("/")
        api_version_clean = api_version.strip("/")
        
        # Remove the API version prefix if present
        if path_only.startswith(api_version_clean):
            service_specific_path = path_only[len(api_version_clean):]
        else:
            service_specific_path = path_only

        # Ensure the path starts with a single "/"
        service_specific_path = "/" + service_specific_path.lstrip("/")

        # Reattach query if it exists
        if parsed.query:
            service_specific_path += f"?{parsed.query}"
            
        self.logger.debug(f"Extracted service-specific path for {service_name}: {service_specific_path}")
        return service_specific_path


    
    def build_url(self, service_name: str, path: str) -> str:
        """
        Build the complete URL for a given microservice, 
        randomly choosing one instance for load balancing.

        Example:
        - Request path: http://127.0.0.1:8000/api/v1/login?token=abc
        - Service: user-service
        - Service instances: ["http://user-service-1:8001", "http://user-service-2:8001"]
        - Returns: http://user-service-2:8001/api/v1/login?token=abc
        """
        service_instances = self.config.services[service_name].instances # List of instance URLs
        api_version = self.config.services[service_name].api_version  # e.g. "/api/v1"
        
        # Pick a random instance for load balancing
        service_instance = random.choice(service_instances)
        
        parsed_base = urlparse(service_instance)
        parsed_path = urlparse(path)

        # Safely combine API version + target path
        new_path = f"{api_version.rstrip('/')}/{parsed_path.path.lstrip('/')}"

        # Build the final URL preserving query and fragment
        final_url = urlunparse((
            parsed_base.scheme,
            parsed_base.netloc,
            new_path,
            '',  # params (rarely used)
            parsed_path.query,
            parsed_path.fragment
        ))

        self.logger.debug(f"Built URL for service {service_name} (instance: {service_instance}): {final_url}")
        return final_url



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
                    health_check_path="/health",
                    api_version=self.settings.USER_SERVICE_URL_API_VERSION
                ),
                "product-service": ServiceConfig(
                    name="product-service",
                    instances=[self.settings.FULL_PRODUCT_SERVICE_URL],
                    health_check_path="/health",
                    api_version=self.settings.PRODUCT_SERVICE_URL_API_VERSION
                ),
                "notification-service": ServiceConfig(
                    name="notification-service",
                    instances=[self.settings.FULL_NOTIFICATION_SERVICE_URL],
                    health_check_path="/health",
                    api_version=self.settings.NOTIFICATION_SERVICE_URL_API_VERSION
                )
                
            }
        )
        self.url_manager = UrlManager(config=self.config, logger=self.logger)

    async def _detect_and_prepare_body(self, request: Request, path: str):
        """
        Detects the content type of the body and prepares it for forwarding.
        Returns: (prepared_body, content_type_header)
        """
        # No body for these methods
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None, None  # No body expected
        
        content_type = request.headers.get("content-type", "").lower()
        
        # Handle JSON
        if "application/json" in content_type:
            try:
                body_data = await request.json()
                return body_data, "application/json"
            except Exception as e:
                logger.warning(f"Failed to parse JSON body for {path}: {e}")
                return None, None
            
        elif "application/x-www-form-urlencoded" in content_type:
            try:
                form_data = await request.form()
                # Convert FormData to dict
                body_dict = {key: form_data[key] for key in form_data.keys()}
                
                # For login, ensure username field exists as OAuth2 expects it (assuming u are passing email and password)
                if path == "/login":
                    form_data = {
                        "username": form_data.get("email") or form_data.get("username"),
                        "password": form_data.get("password")
                    }
                    return form_data, "application/x-www-form-urlencoded"
                
                return body_dict, "application/x-www-form-urlencoded"
            except Exception as e:
                logger.warning(f"Failed to parse form-urlencoded body for {path}: {e}")
                return None, None
            
        elif "multipart/form-data" in content_type:
            try:
                form_data = await request.form()
                # For multipart, we need to handle files differently
                return form_data, "multipart/form-data"
            except Exception as e:
                logger.warning(f"Failed to parse multipart/form-data body for {path}: {e}")
                return None, None

        else:
            try: 
                # Raw body for other content types
                raw_body = await request.body()
                if len(raw_body) == 0:
                    return None, None
                return raw_body, content_type
            except Exception as e:
                logger.warning(f"Failed to read raw body for {path}: {e}")
                return None, None

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
    async def forward_request(self, request: Request, service_name: str) -> JSONResponse:
        """
        Forward request to microservice. 
        Now automatically extracts the correct path based on service mapping.
        """

        if service_name not in self.config.services:
            self.logger.error(f"Service name: {service_name} is not recognized.")
            raise HTTPException(status_code=404, detail="Service not found")

        # Extract the path to forward to the microservice
        service_path = self.url_manager.extract_service_path(str(request.url), service_name)

        # Build the full URL to the microservice
        url = self.url_manager.build_url(service_name, service_path)

        # Detect and prepare body
        prepared_body, content_type = await self._detect_and_prepare_body(request, service_path)
        
        if prepared_body:
            self.logger.debug(f"Prepared body content: {prepared_body}")
        
        # Prepare headers
        headers = self._prepare_headers(request_headers=request.headers, new_content_type=content_type)

        self.logger.info(f"Forwarding request to: {url} with method: {request.method}")
        self.logger.debug(f"Service path: {service_path}")
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
                except orjson.JSONEncodeError:
                    # If response is not JSON, return text
                    content = {"message": response.text, "status_code": response.status_code}

                self.logger.debug(f"Response from {service_name}: status={response.status_code}")

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
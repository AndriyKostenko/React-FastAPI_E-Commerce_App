from email import header
from fastapi import APIRouter, Request

from apigateway import api_gateway_manager
from shared.logger_config import setup_logger

logger = setup_logger(__name__)

user_proxy = APIRouter(tags=["User Service"])


@user_proxy.api_route("/users/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def user_service_proxy(request: Request, path: str, current_user=None):
    """
    Proxy endpoint for user service requests.
    This endpoint forwards requests to the user service based on the path and method.
    """
    # Extract method and body from the request
    method = request.method
    body = await request.body()
    headers = request.headers
    
    logger.info(f"Forwarding request to user service: {path} with method: {method} and body: {body}")
    
    # Forward the request to the user service
    return await api_gateway_manager.forward_request(
        service_key="user-service",
        method=method,
        path=path,
        body=body,
        headers=headers
    )
    
    
    

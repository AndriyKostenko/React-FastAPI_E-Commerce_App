from fastapi import APIRouter, Request

from apigateway import api_gateway_manager
from shared.shared_instances import settings, logger


user_proxy = APIRouter(tags=["User Service"])


@user_proxy.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def user_service_proxy(request: Request, path: str, current_user=None):
    """
    Proxy endpoint for user service requests.
    This endpoint forwards requests to the user service based on the path and method.
    """
    logger.info(f"Forwarding request to user service: {path}, request url: {request.url} with method: {request.method} and body: {await request.body()}")
    
    # Forward the request to the user service
    return await api_gateway_manager.forward_request(
        service_key="user-service",
        method=request.method,
        path=path,
        body=await request.body(),
        headers=request.headers
    )
    
    
    

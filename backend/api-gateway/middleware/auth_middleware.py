from fastapi import Request, HTTPException
import httpx # type: ignore
from shared.shared_instances import settings, logger


async def auth_middleware(request: Request, call_next):
    """
    Authentication middleware to validate JWT tokens for protected endpoints
    """
    # Public endpoints that don't require authentication
    public_endpoints = [
        "/register", "/login", "/token", "/health", "/docs", "/openapi.json",
        "/forgot-password", "/activate", "/password-reset"
    ]
    
    # Check if the current path is public
    path = request.url.path
    is_public = any(path.endswith(endpoint) or endpoint in path for endpoint in public_endpoints)
    
    if is_public:
        logger.info(f"Public endpoint accessed: {path}")
        return await call_next(request)
    
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, 
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header.split(" ")[1]
    
    # Validate token with user service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.FULL_USER_SERVICE_URL}/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                user_data = response.json()
                # Store user data in request state for use in route handlers
                request.state.current_user = user_data
                logger.info(f"Authenticated user: {user_data.get('email')}")
            else:
                logger.warning(f"Token validation failed: {response.status_code}")
                raise HTTPException(
                    status_code=401, 
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"}
                )
                
        except httpx.TimeoutException:
            logger.error("Timeout while validating token with user service")
            raise HTTPException(status_code=503, detail="Authentication service unavailable")
        except httpx.RequestError as e:
            logger.error(f"Error connecting to user service: {e}")
            raise HTTPException(status_code=503, detail="Authentication service unavailable")
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            raise HTTPException(status_code=500, detail="Authentication error")
    
    return await call_next(request)
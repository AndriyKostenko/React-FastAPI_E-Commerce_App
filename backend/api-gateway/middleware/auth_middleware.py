from fastapi import Request, HTTPException
from httpx import AsyncClient, RequestError #type: ignore




class AuthMiddleware:
    """
    Middleware to handle proper access via JWT authentication by validating tokens with the User Service.
    """
    
    PUBLIC_ENDPOINTS = {"/", "/register", "/login", "/token", "/health", "/docs",
                        "/forgot-password", "/activate", "/password-reset"}
        
    @classmethod
    def is_public_endpoint(cls, path: str) -> bool:      
        if path in cls.PUBLIC_ENDPOINTS:
            return True
        return any(path.startswith(prefix) for prefix in cls.PUBLIC_ENDPOINTS)
    
    @classmethod
    async def auth_middleware(cls, request: Request, call_next, logger, settings):
        """
        Middleware function to authenticate requests using JWT tokens.
        """
        path = request.url.path
        logger.debug(f"Auth middleware processing path: {path}")
        
        # 1. Skip authentication for public endpoints
        if cls.is_public_endpoint(path):
            logger.debug(f"Path {path} is public, skipping auth")
            return await call_next(request)
        
        logger.debug(f"Path {path} is protected, checking authentication")
        
        # 2. Extract and validate the Authorization header
        auth_header = request.headers.get("Authorization")
        logger.debug(f"Authorization header: {auth_header[:50] if auth_header else None}...")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        logger.debug(f"Extracted token length: {len(token)}")
        
        # 3. Validate the token with the User Service
        logger.debug("Starting token validation with User Service")
        async with AsyncClient() as client:
            try:
                validation_url = f"{settings.FULL_USER_SERVICE_URL}/me"
                logger.debug(f"Validating token at: {validation_url}")
                
                response = await client.get(
                    validation_url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )
                
                logger.debug(f"User service response status: {response.status_code}")
                
                if response.status_code == 200:
                    user_data = response.json()
                    logger.info(f"Token validated successfully for user: {user_data.get('email', 'unknown')}")
                    # This is the critical line!
                    request.state.current_user = user_data
                    logger.debug(f"Set current_user in request.state: {user_data}")
                else:
                    logger.warning(f"Token validation failed with status: {response.status_code}")
                    raise HTTPException(status_code=401, detail="Invalid token or user not found")
                    
            except RequestError as e:
                logger.error(f"Error connecting to User Service: {e}")
                raise HTTPException(status_code=503, detail="User Service unavailable")
            except Exception as e:
                logger.error(f"Unexpected error during token validation: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        logger.debug("Token validation completed, proceeding to next middleware")
        return await call_next(request)



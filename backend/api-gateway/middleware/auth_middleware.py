from fastapi import Request, HTTPException
import httpx 
from shared.shared_instances import settings



class AuthMiddleware:
    """
    Middleware to handle proper access via JWT authentication by validating tokens with the User Service.
    """
    
    PUBLIC_ENDPOINTS = {"/", "/register", "/login", "/token", "/health", "/docs",
                        "/forgot-password", "/activate", "/password-reset"}
    
    def __init__(self, request: Request, call_next, logger, settings):
        self.request = request
        self.call_next = call_next
        self.logger = logger
        self.settings = settings
        
    @classmethod
    def is_public_endpoint(cls, path: str) -> bool:      
        if path in cls.PUBLIC_ENDPOINTS:
            return True
        return any(path.startswith(prefix) for prefix in cls.PUBLIC_ENDPOINTS)
    
    def get_token_from_header(self, auth_header: str | None) -> str | None:
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        return auth_header.split(" ", 1)[1]
    
    async def validate_token(self, token: str) -> dict | None:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.settings.FULL_USER_SERVICE_URL}/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code == 200:
                    self.logger.info(f"Successfully validated token in auth_middleware")
                    return response.json()
                else:
                    self.logger.warning(f"Invalid or expired token detected in auth_middleware")
                    raise HTTPException(status_code=401, detail="Invalid or expired token",headers={"WWW-Authenticate": "Bearer"})
            except (httpx.TimeoutException, httpx.RequestError) as e:
                self.logger.error(f"Auth service error: {e}")
                raise HTTPException(status_code=503, detail="Authentication service unavailable")
        return None
    
    async def auth_middleware(self):
        path = self.request.url.path
        header = self.request.headers.get("Authorization")
        if self.is_public_endpoint(path):
            return await self.call_next(self.request)
        token = self.get_token_from_header(header)
        if not token:
            self.logger.warning("Missing or malformed Authorization header in auth_middleware")
            raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
        user_data = await self.validate_token(token)
        self.request.state.current_user = user_data
        return await self.call_next(self.request)



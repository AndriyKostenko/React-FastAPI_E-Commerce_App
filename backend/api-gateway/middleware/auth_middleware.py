import httpx
from fastapi import Request, HTTPException, status

from shared.shared_instances import settings


async def auth_middleware(request: Request, call_next):
    # skipiing auth for public endpoints
    public_endpoints = ["/register", "/login", "/token", "/health", "/docs"]
    
    if any(request.url.path.endswith(endpoint) for endpoint in public_endpoints):
        return await call_next(request)
    
    # Extracting and validating JWT token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    token = auth_header.split(" ")[1]

    # Validate the token with the user-service authentication service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.FULL_USER_SERVICE_URL}/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                user_data = response.json()
                # adding user data to the request state
                request.state.current_user = user_data
            else:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        except httpx.RequestError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error connecting to user service: {str(e)}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"User service error: {e.response.text}")

    # If the token is valid, proceed to the next middleware or endpoint
    return await call_next(request)
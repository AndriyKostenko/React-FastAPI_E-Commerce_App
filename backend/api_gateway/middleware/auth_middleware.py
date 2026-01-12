from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from shared.shared_instances import settings, logger
from shared.metaclasses import SingletonMetaClass
from shared.shared_instances import auth_manager


class AuthMiddleware(metaclass=SingletonMetaClass):
    """
    Middleware to handle proper access via JWT authentication by validating tokens with the User Service.
    """

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.PUBLIC_ENDPOINTS = {
            "/health": None,
            "/docs": None,
            "/redoc": None,
            "/openapi.json": None,
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/register": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/login": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/forgot-password": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/activate/": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/password-reset/": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/users": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/products": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/products": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/categories": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/images": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/reviews": ['GET'],

        }

    def is_public_endpoint(self, path: str, method: str) -> bool:
        """Check if the given path is a public endpoint that doesn't require authentication"""
        # Check exact matches
        if path in self.PUBLIC_ENDPOINTS:
            allowed_methods = self.PUBLIC_ENDPOINTS[path]
            if allowed_methods is None:
                return True
            return method in allowed_methods


        for endpoint_prefix, allowed_methods in self.PUBLIC_ENDPOINTS.items():
            if path.startswith(endpoint_prefix):
                if allowed_methods is None:
                    return True
                return method in allowed_methods
        return False

    async def middleware(self, request: Request, call_next):
        """
        Main middleware function to authenticate requests using JWT tokens.
        """
        path = request.url.path
        method = request.method
        self.logger.info(f"🔍 Auth middleware processing: {method} {path}")

        # 1. Skip authentication for public endpoints
        is_public = self.is_public_endpoint(path, method)
        self.logger.info(f"🔍 Is path '{path}' public? {is_public}")

        if is_public:
            self.logger.info(f"Path {path} is public, skipping auth")
            return await call_next(request)

        self.logger.info(f"Path {path} requires authentication")

        # 2. Extract and validate the Authorization header
        auth_header = request.headers.get("Authorization")
        self.logger.info(f"🔍 Authorization header present: {auth_header is not None}")

        if not auth_header or not auth_header.startswith("Bearer "):
            self.logger.warning("Missing or invalid Authorization header")
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header",
                         "error": "missing_authorization_header"}
            )

        token = auth_header.split(" ")[1]
        self.logger.info(f"🔍 Extracted token (first 20 chars): {token[:20]}...")

        # 3. Validate the token with the User Service
        try:
            # Use shared auth manager to decode token
            user_data = auth_manager.decode_token(token)

            # Attach user data to request state for downstream access
            request.state.current_user = user_data
            self.logger.info(f"Token is validated for: {user_data.get('email')}")
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail, "error": "invalid_token"}
            )
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token validation failed", "error": "invalid_token"}
            )

        return await call_next(request)


auth_middleware = AuthMiddleware(settings, logger)

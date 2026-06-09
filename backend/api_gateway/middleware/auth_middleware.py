from logging import Logger
from fastapi import Request, HTTPException, Response
from fastapi.responses import JSONResponse

from shared.shared_instances import settings, logger, token_manager
from shared.utils.metaclasses import SingletonMetaClass
from shared.settings import Settings
from shared.enums.auth_enums import AuthCookies

class AuthMiddleware(metaclass=SingletonMetaClass):
    """
    Middleware to handle proper access via JWT authentication by validating tokens with the User Service.
    """
    def __init__(self, settings: Settings, logger: Logger):
        self.settings: Settings = settings
        self.logger: Logger = logger
        self.PUBLIC_ENDPOINTS: dict[str, list[str] | None] = {
            "/health": None,
            "/metrics": None,
            "/media": None,
            "/docs": None,
            "/redoc": None,
            "/openapi.json": None,
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/register": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/login": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/google-login": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/refresh": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/logout": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/forgot-password": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/activate/": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/password-reset/": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/products": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/categories": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/customization/pricing": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/images/generations/": ['GET'],  # job status poll
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/images/generations": ['POST'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/users": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/products": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/categories": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/images": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/reviews": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/admin/schema/orders": ['GET'],
            f"{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/payments/webhook": ['POST'],

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
        Checks `access_token` **cookie first**, falls back to `Authorization: Bearer` header (so Swagger UI keeps working)
        """
        path, method = request.url.path, request.method
        self.logger.info(f"🔍 Auth middleware processing: {method} {path}")
        # Always pass OPTIONS (CORS preflight) through — CORSMiddleware handles it
        if method == "OPTIONS":
            return await call_next(request)
        # 1. Check if this is a public endpoint
        is_public = self.is_public_endpoint(path, method)
        self.logger.info(f"🔍 Is path: '{path}' public?  - {is_public}")
        # 2. Extract token: prefer HttpOnly cookie, fall back to Authorization header
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            self.logger.info(f"🔍 Authorization header present: {auth_header is not None}")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        # 3. Try to validate token if present (required for protected endpoints, optional for public)
        if token:
            try:
                user_data = token_manager.decode_token(token)
                request.state.current_user = user_data
                self.logger.info(f"Token is validated for: {user_data.email}")
            except HTTPException as exc:
                if not is_public:
                    return JSONResponse(
                        status_code=exc.status_code,
                        content={"detail": exc.detail, "error": "invalid_token"}
                    )
                self.logger.warning(f"Token validation failed for public endpoint: {exc.detail}")
            except Exception:
                if not is_public:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Token validation failed", "error": "invalid_token"}
                    )
                self.logger.warning("Token validation failed for public endpoint")
        elif not is_public:
            # Token is required for protected endpoints
            self.logger.warning("Missing or invalid Authorization header and no access_token cookie")
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header",
                         "error": "missing_authorization_header"}
            )
        else:
            self.logger.info(f"Path: {path} is public, no token provided")

        return await call_next(request)

    def set_auth_cookies(self,
                          response: Response,
                          access_token: str,
                          refresh_token: str | None) -> None:
        """Set HttpOnly auth cookies on the response. Pass refresh_token=None to skip it (token rotation)."""
        secure = self.settings.SECURE_COOKIES
        response.set_cookie(
            key=AuthCookies.ACCESS_COOKIE,
            value=access_token,
            httponly=True, # Prevent JavaScript access to mitigate XSS risks
            secure=secure, # Only send cookies over HTTPS in production
            samesite="lax", # CSRF protection
            max_age=self.settings.TOKEN_TIME_DELTA_MINUTES * 60, # Access token expires in minutes, convert to seconds for max_age
        )
        if refresh_token is not None:
            response.set_cookie(
                key=AuthCookies.REFRESH_COOKIE,
                value=refresh_token,
                httponly=True,
                secure=secure,
                samesite="lax",
                max_age=self.settings.REFRESH_TOKEN_TIME_DELTA_DAYS * 86400, # Refresh token expires in days, convert to seconds
            )

    def clear_auth_cookies(self, response: Response) -> None:
        """Clear auth cookies (logout)."""
        secure = self.settings.SECURE_COOKIES
        response.delete_cookie(key=AuthCookies.ACCESS_COOKIE, httponly=True, secure=secure, samesite="lax")
        response.delete_cookie(key=AuthCookies.REFRESH_COOKIE, httponly=True, secure=secure, samesite="lax")


auth_middleware = AuthMiddleware(settings, logger)

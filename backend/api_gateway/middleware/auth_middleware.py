from logging import Logger
from fastapi import Request, HTTPException, Response
from fastapi.responses import JSONResponse

from shared.settings import Settings
from shared.managers.session_registry import SessionRegistry
from shared.managers.token_manager import TokenManager
from shared.enums.auth_enums import AuthCookies
from middleware.public_routes import PublicRouteRegistry

class AuthMiddleware:
    """
    Middleware to handle proper access via JWT authentication by validating tokens with the User Service.
    """
    def __init__(
        self,
        settings: Settings,
        logger: Logger,
        token_manager: TokenManager,
        session_registry: "SessionRegistry | None" = None,
    ):
        self.settings: Settings = settings
        self.logger: Logger = logger
        self.token_manager = token_manager
        # Decoding a token proves it was issued and has not expired; it says
        # nothing about whether the user has since revoked it. Only this
        # service authenticates the requests that never reach user-service, so
        # without the registry a password reset would leave stolen access
        # tokens working until they expired on their own.
        self.session_registry = session_registry
        # Secure by default: anything not declared here requires a session.
        # Paths match on segment boundaries, never on a raw string prefix.
        self.public_routes = PublicRouteRegistry.for_api_version(
            self.settings.API_GATEWAY_SERVICE_URL_API_VERSION
        )

    def is_public_endpoint(self, path: str, method: str) -> bool:
        """Check if the given path is a public endpoint that doesn't require authentication"""
        return self.public_routes.is_public(path, method)

    def is_cacheable_endpoint(self, path: str, method: str) -> bool:
        """Check if a response may be shared from cache with every caller"""
        return self.public_routes.is_cacheable(path, method)

    async def _is_revoked(self, user_data) -> bool:
        """Report whether this token predates the user's current session generation."""
        if self.session_registry is None:
            return False
        revoked = await self.session_registry.is_revoked(
            user_data.id, user_data.token_version
        )
        if revoked:
            self.logger.warning(
                "Rejected a revoked session for user %s (token generation %s)",
                user_data.id,
                user_data.token_version,
            )
        return revoked

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
                user_data = self.token_manager.decode_token(token)
                if await self._is_revoked(user_data):
                    raise HTTPException(
                        status_code=401,
                        detail="Session has been revoked. Please sign in again.",
                    )
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

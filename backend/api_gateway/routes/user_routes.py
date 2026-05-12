from uuid import UUID

from orjson import loads
from fastapi import APIRouter, Request, Response, Depends, status

from gateway.apigateway import api_gateway_manager
from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from shared.schemas.user_schemas import CurrentUserInfo
from shared.utils.customized_json_response import JSONResponse
from middleware.auth_middleware import auth_middleware
from shared.enums.services_enums import Services
from shared.enums.auth_enums import AuthCookies
from shared.shared_instances import api_gateway_redis_manager


user_proxy = APIRouter(tags=["User Service Proxy"])

# ==================== PUBLIC ENDPOINTS (No Auth) ====================

@user_proxy.post("/register", summary="Register a new user")
@api_gateway_redis_manager.ratelimiter(times=5, seconds=3600)
async def register_user(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
    )


@user_proxy.post("/login", summary="User login")
@api_gateway_redis_manager.ratelimiter(times=5, seconds=60)
async def login_user(request: Request, response: Response) -> JSONResponse:
    """
    Gateway forwards form data to user service → gets JSON with tokens.
    - `refresh_token` is stripped from the body and set as HttpOnly cookie only (long-lived, sensitive).
    - `access_token` is kept in the body AND set as HttpOnly cookie:
        * Cookie is used by the browser for subsequent API calls.
        * Body value is needed by NextAuth's server-side `authorize()` which cannot read Set-Cookie headers.
    """
    upstream = await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
    )
    if upstream.status_code == 200:
        body: dict[str, str] = loads(upstream.body)
        refresh_token = body.pop(AuthCookies.REFRESH_COOKIE)
        access_token = body[AuthCookies.ACCESS_COOKIE]
        response = JSONResponse(
            content=body,
            status_code=status.HTTP_200_OK
        )
        auth_middleware.set_auth_cookies(
            response=response,
            access_token=access_token,
            refresh_token=refresh_token
        )
        return response
    return upstream


@user_proxy.post("/refresh", summary="Refresh access token")
@api_gateway_redis_manager.ratelimiter(times=10, seconds=60)
async def refresh_token(request: Request, response: Response) -> JSONResponse:
    """
    Gateway reads `refresh_token` cookie → forwards `{"refresh_token": ...}` to user service
    Sets a new `access_token` cookie
    """
    refresh = request.cookies.get(AuthCookies.REFRESH_COOKIE)
    if not refresh:
        return JSONResponse(
            content={"detail": "Refresh token cookie missing"},
            status_code=401,
        )
    upstream = await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
        override_body={AuthCookies.REFRESH_COOKIE: refresh},
    )
    if upstream.status_code == 200:
        body = loads(upstream.body)
        auth_middleware.set_auth_cookies(
            response,
            access_token=body.pop(AuthCookies.ACCESS_COOKIE),
            refresh_token=None,
        )
        return JSONResponse(content=body, status_code=200)
    return upstream


@user_proxy.post("/logout", summary="Logout and revoke refresh token")
@api_gateway_redis_manager.ratelimiter(times=10, seconds=60)
async def logout(request: Request, response: Response) -> JSONResponse:
    """
    Gateway reads `refresh_token` cookie → revokes it in Redis via user service
    - **Clears both cookies** immediately
    """
    refresh = request.cookies.get(AuthCookies.REFRESH_COOKIE)
    auth_middleware.clear_auth_cookies(response)
    if refresh:
        await api_gateway_manager.forward_request(
            request=request,
            service_name=Services.USER_SERVICE,
            override_body={"refresh_token": refresh},
        )
    return JSONResponse(content={"detail": "Logged out successfully"}, status_code=200)


@user_proxy.post("/activate/{token}", summary="Verify user email")
@api_gateway_redis_manager.ratelimiter(times=5, seconds=3600)
async def verify_email(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )

@user_proxy.post("/forgot-password", summary="Request password reset")
@api_gateway_redis_manager.ratelimiter(times=3, seconds=3600)
async def forgot_password(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )

@user_proxy.post("/password-reset/{token}", summary="Reset password with token")
@api_gateway_redis_manager.ratelimiter(times=3, seconds=3600)
async def reset_password(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )

# ==================== AUTHENTICATED USER ENDPOINTS ====================

@user_proxy.get("/me", summary="Get current user data")
@api_gateway_redis_manager.ratelimiter(times=3, seconds=3600)
async def get_current_user_data(request: Request,
                                current_user: CurrentUserInfo = Depends(get_current_user)) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request
    )


# ==================== ADMIN OR SELF ENDPOINTS ====================


@user_proxy.get("/users/{user_id}", summary="Get user by ID")
@api_gateway_redis_manager.cached(ttl=60)
@api_gateway_redis_manager.ratelimiter(times=10, seconds=60)
async def get_user_by_id(request: Request,
                         user_id: UUID,
                         current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )


@user_proxy.patch("/users/{user_id}", summary="Update user by ID")
async def update_user_by_id(request: Request,
                            user_id: UUID,
                            current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )


@user_proxy.delete("/users/{user_id}", summary="Delete user by ID")
async def delete_user_by_id(request: Request,
                            user_id: UUID,
                            current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )


# ==================== ADMIN ONLY ENDPOINTS ====================

@user_proxy.get("/users", summary="Get all users")
async def get_all_users(request: Request,
                        current_user: CurrentUserInfo = Depends(require_admin)):
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )


# ==================== ADMINJS ENDPOINTS ====================

@user_proxy.get("/admin/schema/users")
async def get_user_schema_for_admin_js(request: Request):
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request
    )

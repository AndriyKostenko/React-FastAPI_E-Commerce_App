from uuid import UUID

from orjson import loads
from fastapi import APIRouter, Request, Depends, status

from resources import api_gateway_manager, get_api_gateway_resources, rate_limited
from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from shared.contracts.auth import TokenClaims as CurrentUserInfo
from shared.utils.customized_json_response import JSONResponse
from shared.enums.services_enums import Services
from shared.enums.auth_enums import AuthCookies


user_proxy = APIRouter(tags=["User Service Proxy"])

# ==================== PUBLIC ENDPOINTS (No Auth) ====================

@user_proxy.post("/register", summary="Register a new user")
@rate_limited(times=5, seconds=3600)
async def register_user(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE)


def _signed_in_response(request: Request, upstream: JSONResponse) -> JSONResponse:
    """
    Turn user-service's token body into the session the browser keeps.

    - `refresh_token` leaves the body and travels only as an HttpOnly cookie
      (long-lived, sensitive). On a refresh it is the *rotated* one: user-service
      has already spent the old one, so keeping the old cookie would make the
      next refresh look like token theft and end every session.
    - `access_token` stays in the body AND is set as an HttpOnly cookie: the
      body serves server-side callers (NextAuth's `authorize()`, admin-js) that
      cannot read Set-Cookie, the cookie the browser's own API calls.

    The cookies are set on the response that is returned. FastAPI drops headers
    set on the injected `response` parameter whenever a route returns its own
    Response, which is how /refresh and /logout used to set nothing at all.
    """
    if upstream.status_code != status.HTTP_200_OK:
        return upstream
    body: dict[str, str | int | None] = loads(upstream.body)
    refresh_token = body.pop(AuthCookies.REFRESH_COOKIE, None)
    body.pop("refresh_token_expiry", None)
    access_token = body[AuthCookies.ACCESS_COOKIE]
    response = JSONResponse(content=body, status_code=status.HTTP_200_OK)
    get_api_gateway_resources(request).auth.set_auth_cookies(
        response=response,
        access_token=str(access_token),
        refresh_token=str(refresh_token) if refresh_token else None,
    )
    return response


@user_proxy.post("/login", summary="User login")
@rate_limited(times=5, seconds=60)
async def login_user(request: Request) -> JSONResponse:
    """Password sign-in. Admin accounts are refused here: they sign in with a passkey."""
    upstream = await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
    )
    return _signed_in_response(request, upstream)


@user_proxy.post("/google-login", summary="Login or register with Google OAuth")
@rate_limited(times=10, seconds=60)
async def google_login(request: Request) -> JSONResponse:
    """
    Accepts a Google ID token, verifies it via the user service, and returns an app JWT.
    Sets the same HttpOnly auth cookies as the regular login endpoint.
    """
    upstream = await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
    )
    return _signed_in_response(request, upstream)


@user_proxy.post("/login/passkey/options", summary="Passkey sign-in, step 1: password, then a challenge")
@rate_limited(times=5, seconds=60)
async def passkey_login_options(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
    )


@user_proxy.post("/login/passkey/verify", summary="Passkey sign-in, step 2: the signed challenge")
@rate_limited(times=5, seconds=60)
async def passkey_login_verify(request: Request) -> JSONResponse:
    upstream = await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
    )
    return _signed_in_response(request, upstream)


@user_proxy.post("/passkeys/enrolment/options", summary="Passkey enrolment, step 1 (one-time link token)")
@rate_limited(times=5, seconds=60)
async def passkey_enrolment_options(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
    )


@user_proxy.post("/passkeys/enrolment/verify", summary="Passkey enrolment, step 2: the new credential")
@rate_limited(times=5, seconds=60)
async def passkey_enrolment_verify(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
    )


@user_proxy.post("/refresh", summary="Refresh access token")
@rate_limited(times=10, seconds=60)
async def refresh_token(request: Request) -> JSONResponse:
    """
    Gateway reads the `refresh_token` cookie, forwards `{"refresh_token": ...}`
    to user service, and sets the new access token and the rotated refresh
    token as cookies.
    """
    refresh = request.cookies.get(AuthCookies.REFRESH_COOKIE)
    if not refresh:
        return JSONResponse(
            content={"detail": "Refresh token cookie missing"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    upstream = await api_gateway_manager.forward_request(
        request=request,
        service_name=Services.USER_SERVICE,
        override_body={AuthCookies.REFRESH_COOKIE: refresh},
    )
    return _signed_in_response(request, upstream)


@user_proxy.post("/logout", summary="Logout and revoke refresh token")
@rate_limited(times=10, seconds=60)
async def logout(request: Request) -> JSONResponse:
    """
    Gateway reads `refresh_token` cookie → revokes it in Redis via user service
    - **Clears both cookies** on the response it returns
    """
    refresh = request.cookies.get(AuthCookies.REFRESH_COOKIE)
    if refresh:
        await api_gateway_manager.forward_request(
            request=request,
            service_name=Services.USER_SERVICE,
            override_body={"refresh_token": refresh},
        )
    response = JSONResponse(content={"detail": "Logged out successfully"}, status_code=status.HTTP_200_OK)
    get_api_gateway_resources(request).auth.clear_auth_cookies(response)
    return response


# The single-use token travels in the request body, not the path: a URL path
# lands in access logs, proxy logs, browser history and Referer headers, and
# these tokens are credentials.
@user_proxy.post("/activate", summary="Verify user email")
@rate_limited(times=5, seconds=3600)
async def verify_email(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )

@user_proxy.post("/forgot-password", summary="Request password reset")
@rate_limited(times=3, seconds=3600)
async def forgot_password(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )

@user_proxy.post("/password-reset", summary="Reset password with token")
@rate_limited(times=3, seconds=3600)
async def reset_password(request: Request) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request,
    )

# ==================== AUTHENTICATED USER ENDPOINTS ====================

@user_proxy.get("/me", summary="Get current user data")
# Polled on every page load by the frontend session check — this is a normal
# read, not a credential operation, so it gets a read-shaped limit.
@rate_limited(times=60, seconds=60)
async def get_current_user_data(request: Request,
                                current_user: CurrentUserInfo = Depends(get_current_user)) -> JSONResponse:
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request
    )


# ==================== ADMIN OR SELF ENDPOINTS ====================


@user_proxy.get("/users/{user_id}", summary="Get user by ID")
@rate_limited(times=10, seconds=60)
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
async def get_user_schema_for_admin_js(
    request: Request,
    admin: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name=Services.USER_SERVICE,
        request=request
    )

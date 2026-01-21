from uuid import UUID

import orjson
from fastapi import APIRouter, Request, Depends

from apigateway import api_gateway_manager
from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from shared.schemas.user_schemas import CurrentUserInfo
from shared.
from shared.customized_json_response import JSONResponse


user_proxy = APIRouter(tags=["User Service Proxy"])


# ==================== PUBLIC ENDPOINTS (No Auth) ====================

@user_proxy.post("/register", summary="Register a new user")
async def register_user(request: Request):
    user_service_response = await api_gateway_manager.forward_request(
        request=request,
        service_name="user-service",
    )
    # Check if registration was successful
    if user_service_response.status_code != 201:
        return user_service_response
    # parsing the response content (new user data + token)
    response_data = orjson.loads(user_service_response.body)
    # publishing the event with token
    await events_publisher.publish_user_registered(
        email=response_data["email"],
        token=response_data["verification_token"]
        )
    # Remove token from response !!!
    del response_data["verification_token"]
    return JSONResponse(
        content=response_data,
        status_code=user_service_response.status_code
    )


@user_proxy.post("/login", summary="User login")
async def login_user(request: Request):
    # passing form data as body to user service coz it expects form data for OAuth2
    # so we need to forward the form data as is
    user_service_response = await api_gateway_manager.forward_request(
        request=request,
        service_name="user-service",
    )
    # Check if login was successful
    if user_service_response.status_code != 200:
        return user_service_response
    # publish the login event
    response_data = orjson.loads(user_service_response.body)
    await events_publisher.publish_user_login(
        email=response_data["user_email"],
    )
    return JSONResponse(
        content=response_data,
        status_code=user_service_response.status_code
    )

@user_proxy.post("/activate/{token}", summary="Verify user email")
async def verify_email(request: Request):
    return await api_gateway_manager.forward_request(
        service_name="user-service",
        request=request,
    )

@user_proxy.post("/forgot-password", summary="Request password reset")
async def forgot_password(request: Request):
    user_service_response =  await api_gateway_manager.forward_request(
        service_name="user-service",
        request=request,
    )
    if user_service_response.status_code != 200: return user_service_response
    response_data = orjson.loads(user_service_response.body)
    await events_publisher.publish_password_reset_request(email=response_data["email"],
                                                          reset_token=response_data["reset_token"])
    del response_data["reset_token"]
    return JSONResponse(content=response_data,
                        status_code=user_service_response.status_code)


@user_proxy.post("/password-reset/{token}", summary="Reset password with token")
async def reset_password(request: Request):
    user_service_response =  await api_gateway_manager.forward_request(
        service_name="user-service",
        request=request,
    )
    if user_service_response.status_code != 200: return user_service_response
    response_data = orjson.loads(user_service_response.body)
    await events_publisher.publish_password_reset_seccess(email=response_data["email"])
    return JSONResponse(content=response_data,
                        status_code=user_service_response.status_code)



# ==================== AUTHENTICATED USER ENDPOINTS ====================



# Protected endpoints with dependencies
@user_proxy.get("/me", summary="Get current user data")
async def get_current_user_data(request: Request,
                                current_user: CurrentUserInfo = Depends(get_current_user)):
    return await api_gateway_manager.forward_request(
        service_name="user-service",
        request=request
    )


# ==================== ADMIN OR SELF ENDPOINTS ====================


@user_proxy.get("/users/{user_id}", summary="Get user by ID")
async def get_user_by_id(request: Request,
                         user_id: UUID,
                         current_user: CurrentUserInfo = Depends(get_current_user)):
    # Check authorization using the dependency function
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name="user-service",
        request=request,
    )


@user_proxy.patch("/users/{user_id}", summary="Update user by ID")
async def update_user_by_id(request: Request,
                            user_id: UUID,
                            current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name="user-service",
        request=request,
    )


@user_proxy.delete("/users/{user_id}", summary="Delete user by ID")
async def delete_user_by_id(request: Request,
                            user_id: UUID,
                            current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name="user-service",
        request=request,
    )


# ==================== ADMIN ONLY ENDPOINTS ====================

@user_proxy.get("/users", summary="Get all users")
async def get_all_users(request: Request,
                        current_user: CurrentUserInfo = Depends(require_admin)):
    return await api_gateway_manager.forward_request(
        service_name="user-service",
        request=request,
    )


# ==================== ADMINJS ENDPOINTS ====================

@user_proxy.get("/admin/schema/users")
async def get_user_schema_for_admin_js(request: Request):
    # for noew its unprotected, but later we can add admin auth if needed
    return await api_gateway_manager.forward_request(
        service_name="user-service",
        request=request
    )

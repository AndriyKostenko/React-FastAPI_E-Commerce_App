from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from shared.customized_json_response import JSONResponse
from shared.shared_instances import settings, user_service_redis_manager

from dependencies.dependencies import user_service_dependency
from dependencies.dependencies import get_current_user
from models.user_models import User
from events_publisher.user_events_publisher import notification_events_publisher
from shared.schemas.user_schemas import (
    CurrentUserInfo,
    EmailVerificationResponse,
    ForgotPasswordResponse,
    PasswordUpdateResponse,
    ResetPasswordRequest,
    UserBasicUpdate,
    UserInfo,
    UserLoginDetails,
    UsersFilterParams,
    UserSignUp,
)

user_routes = APIRouter(tags=["users"])

"""
Usefull tips / rules in that module:
1. Using `Depends(get_user_service)` to inject the user service dependency.
2. Using `BackgroundTasks` to send emails without blocking the request.
3. Using `ratelimiter` decorator to apply rate limiting to endpoints.
    - each endpoint should have "request: Request" parameter for rate limiting to work
    - GET endpoints: Use both caching and rate limiting
    - POST/PUT/DELETE endpoints: Use rate limiting and cache invalidation
    - Security-sensitive endpoints (login, password reset): Stricter rate limits
    - Data retrieval endpoints: More lenient rate limits with caching
    - Email-related endpoints: Strict rate limits to prevent spam

4. Using `cached` decorator to cache GET responses.
    - cache responses using aio Redis for improving performance
    - GET endpoints: Use both caching and rate limiting
    - cache key should be unique per user, e.g. by email or user ID
    - Use `invalidate_cache` to clear cache when user data changes.

5. All potential exceptions are handled in
the service layer, so no need to handle them here.
6. All data returned according to Pydantic schemas in service layer.
7. Use `JSONResponse` for consistent response format and getting data and status codes for caching / ratelimiting.
"""


@user_routes.post("/register",
                  summary="Create new user",
                  response_description="New user created successfully",
                  response_model=UserInfo)
@user_service_redis_manager.ratelimiter(times=5, seconds=3600)
async def create_user(request: Request,
                      data: UserSignUp,
                      user_service: user_service_dependency):
    new_db_user, verification_token = await user_service.create_user(data=data)
    await notification_events_publisher.publish_user_registered(new_db_user.email,verification_token)
    await user_service_redis_manager.clear_cache_namespace(request, "users")
    return JSONResponse(content=new_db_user,status_code=status.HTTP_201_CREATED)


@user_routes.post("/activate/{token}",
                  summary="Verify user email",
                  response_description="Email verified successfully",)
@user_service_redis_manager.ratelimiter(times=5, seconds=3600)
async def verify_email(request: Request, token: str, user_service: user_service_dependency):
    db_user = await user_service.verify_email(token=token)
    return JSONResponse(
        content=EmailVerificationResponse(
            detail="Email verified successfully",
            email=db_user.email,
            verified=db_user.is_verified,
        ),
        status_code=status.HTTP_200_OK,
    )


@user_routes.post("/forgot-password",
                    summary="Request password reset",
                    response_description="Password reset email sent successfully",
                    response_model=ForgotPasswordResponse)
@user_service_redis_manager.ratelimiter(times=3, seconds=3600)
async def forgot_password(request: Request, email: EmailStr, user_service: user_service_dependency):
    await user_service.request_password_reset(email)
    return JSONResponse(
        content=ForgotPasswordResponse(
            detail="Password reset email has been sent!",
            email=email,
        ),
        status_code=status.HTTP_200_OK,
    )

# TODO: refactore the token_data acc unfo (place into business logic in user_service)
@user_routes.post("/password-reset/{token}",
                    summary="Reset password with token",
                    response_model=PasswordUpdateResponse,
                    response_description="Password reset successfully")
@user_service_redis_manager.ratelimiter(times=3, seconds=3600)
async def reset_password(request: Request, token: str, data: ResetPasswordRequest, user_service: user_service_dependency):
    """Reset password using token"""
    user = await user_service.reset_password_with_token(token=token, new_password=data.new_password)
    # Invalidate user-specific caches only
    await user_service_redis_manager.clear_cache_namespace(namespace="users", request=request)
    await user_service_redis_manager.clear_cache_namespace(namespace="me", request=request)
    return JSONResponse(
        content=PasswordUpdateResponse(
            detail="Password reset successfully", email=user.email
        ),
        status_code=status.HTTP_200_OK,
    )


@user_routes.post("/login",
                    summary="User login",
                    response_model=UserLoginDetails,
                    response_description="User logged in successfully")
@user_service_redis_manager.ratelimiter(times=5, seconds=60)
async def login(request: Request,
                form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                user_service: user_service_dependency):  # request is reqired for rate limiting decorator
    user, access_token, expiry_timestamp = await user_service.login_user(form_data)
    return JSONResponse(
        content=UserLoginDetails(
            access_token=access_token,
            token_type=settings.TOKEN_TYPE,
            token_expiry=expiry_timestamp,
            user_id=user.id,
            user_email=user.email,
            user_role=user.role,
        ),
        status_code=status.HTTP_200_OK,
    )


@user_routes.get("/me")
async def get_me(current_user: CurrentUserInfo = Depends(get_current_user)):
    return current_user



# --------------------------Users------------------------------------


@user_routes.get(
    "/users/{user_id}",
    summary="Get user by id",
    response_description="User data retrieved successfully",
    response_model=UserInfo,
)
@user_service_redis_manager.cached(ttl=60)
@user_service_redis_manager.ratelimiter(times=10, seconds=60)
async def get_user_by_user_id(
    request: Request, user_id: UUID, user_service: user_service_dependency
):
    user = await user_service.get_user_by_id(user_id=user_id)
    return JSONResponse(content=user, status_code=status.HTTP_200_OK)


@user_routes.get(
    "/users",
    summary="Get all users",
    response_description="List of all users retrieved successfully",
    response_model=list[UserInfo],
)
@user_service_redis_manager.cached(ttl=60)
@user_service_redis_manager.ratelimiter(times=10, seconds=60)
async def get_all_users(
    request: Request,
    user_service: user_service_dependency,
    filters_query: Annotated[UsersFilterParams, Query()],
):
    users = await user_service.get_all_users(filters=filters_query)
    return JSONResponse(content=users, status_code=status.HTTP_200_OK)


@user_routes.patch(
    "/users/{user_id}",
    summary="Update user by ID",
    response_description="User updated successfully",
    response_model=UserInfo,
)
@user_service_redis_manager.ratelimiter(times=5, seconds=3600)
async def update_user_by_id(
    request: Request,
    user_id: UUID,
    data: UserBasicUpdate,
    user_service: user_service_dependency,
):
    updated_user = await user_service.update_user_basic_info(
        user_id=user_id, update_data=data
    )

    # Invalidate cache for user list and related endpoints, adding force_method to ensure correct cache keys are targeted
    await user_service_redis_manager.clear_cache_namespace(
        namespace="users",
        request=request,
    )
    await user_service_redis_manager.clear_cache_namespace(
        namespace="me", request=request
    )
    return JSONResponse(content=updated_user, status_code=status.HTTP_200_OK)


@user_routes.delete(
    "/users/{user_id}",
    summary="Delete user by ID",
    response_description="User deleted successfully",
)
@user_service_redis_manager.ratelimiter(times=5, seconds=3600)
async def delete_user_by_id(
    request: Request, user_id: UUID, user_service: user_service_dependency
):
    await user_service.delete_user_by_id(user_id=user_id)

    # Invalidate cache for user list and related endpoints, adding force_method to ensure correct cache keys are targeted
    await user_service_redis_manager.clear_cache_namespace(
        namespace="users", request=request
    )
    await user_service_redis_manager.clear_cache_namespace(
        namespace="me", request=request
    )

    return JSONResponse(
        content={"detail": "User deleted successfully"}, status_code=status.HTTP_200_OK
    )


# -------------------------AdminJS Schema-----------------------------------


@user_routes.get(
    "/admin/schema/users",
    summary="Get schema for AdminJS",
)
@user_service_redis_manager.cached(ttl=60)
@user_service_redis_manager.ratelimiter(
    times=10, seconds=60
)  # Limit to 10 requests per minute
async def get_user_schema_for_admin_js(request: Request):
    return JSONResponse(
        content={"fields": User.get_admin_schema()}, status_code=status.HTTP_200_OK
    )

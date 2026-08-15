from typing import Annotated
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr

from resources import rate_limited, settings
from dependencies.dependencies import (
    user_service_dependency,
    current_user_dependency,
    admin_only_dependency,
    self_or_admin_dependency,
)
from models.user_models import User
from schemas.user_schemas import (
    EmailVerificationResponse,
    ActivationRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleLoginRequest,
    PasswordUpdateResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ResetPasswordRequest,
    CurrentUserInfo,
    UserBasicUpdate,
    UserInfo,
    UserLoginDetails,
    UsersFilterParams,
    UserSignUp,
)

user_routes = APIRouter(tags=["users"])

@user_routes.post("/register",
                  summary="Create new user",
                  response_description="New user created successfully",
                  response_model=UserInfo,
                  status_code=status.HTTP_201_CREATED)
@rate_limited(times=20, seconds=3600)
async def create_user(request: Request, data: UserSignUp,
                      user_service: user_service_dependency):
    new_db_user, verification_token = await user_service.create_user(data=data)
    return new_db_user

@user_routes.post("/activate",
                  summary="Verify user email",
                  response_description="Email verified successfully",
                  response_model=EmailVerificationResponse,
                  status_code=status.HTTP_200_OK)
@rate_limited(times=15, seconds=3600)
async def verify_email(request: Request, data: ActivationRequest, user_service: user_service_dependency):
    db_user = await user_service.verify_email(token=data.token)
    return EmailVerificationResponse(
        detail="Email verified successfully",
        email=db_user.email,
        verified=db_user.is_verified,
    )

@user_routes.post("/forgot-password",
                  summary="Request password reset",
                  response_description="Password reset email sent successfully",
                  response_model=ForgotPasswordResponse,
                  status_code=status.HTTP_200_OK)
@rate_limited(times=10, seconds=3600, identifier_param="data")
async def forgot_password(request: Request, data: ForgotPasswordRequest, user_service: user_service_dependency):
    user, reset_token = await user_service.request_password_reset(data.email)
    return ForgotPasswordResponse(
        detail="If that email exists, a password reset email has been sent.",
        email=data.email,
    )

@user_routes.post("/password-reset",
                  summary="Reset password with token",
                  response_model=PasswordUpdateResponse,
                  response_description="Password reset successfully",
                  status_code=status.HTTP_200_OK)
@rate_limited(times=15, seconds=3600)
async def reset_password(request: Request, data: ResetPasswordRequest, user_service: user_service_dependency):
    """Reset password using token"""
    user = await user_service.reset_password_with_token(token=data.token, new_password=data.new_password)
    return PasswordUpdateResponse(
        detail="Password reset successfully", email=user.email
    )

@user_routes.post("/login",
                  summary="User login",
                  response_model=UserLoginDetails,
                  response_description="User logged in successfully",
                  status_code=status.HTTP_200_OK)
@rate_limited(times=10, seconds=60, identifier_param="form_data")
async def login(request: Request,
                form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                user_service: user_service_dependency):
    user, access_token, access_expiry, refresh_token, refresh_expiry = await user_service.login_user(form_data)
    return UserLoginDetails(
        access_token=access_token,
        token_type=settings.TOKEN_TYPE,
        token_expiry=access_expiry,
        refresh_token=refresh_token,
        refresh_token_expiry=refresh_expiry,
        user_id=user.id,
        user_email=user.email,
        user_role=user.role,
    )

@user_routes.post("/google-login",
                  summary="Login or register with Google",
                  response_model=UserLoginDetails,
                  response_description="Authenticated successfully via Google",
                  status_code=status.HTTP_200_OK)
@rate_limited(times=10, seconds=60, identifier_param="data")
async def google_login(request: Request, data: GoogleLoginRequest,
                       user_service: user_service_dependency):
    user, access_token, access_expiry, refresh_token, refresh_expiry = await user_service.login_or_register_google_user(data.id_token)
    return UserLoginDetails(
        access_token=access_token,
        token_type=settings.TOKEN_TYPE,
        token_expiry=access_expiry,
        refresh_token=refresh_token,
        refresh_token_expiry=refresh_expiry,
        user_id=user.id,
        user_email=user.email,
        user_role=user.role,
    )

@user_routes.post("/refresh",
                  summary="Refresh access token",
                  response_model=RefreshTokenResponse,
                  response_description="New access token issued",
                  status_code=status.HTTP_200_OK)
@rate_limited(times=30, seconds=60)
async def refresh_token(request: Request, data: RefreshTokenRequest,
                        user_service: user_service_dependency):
    access_token, expiry, new_refresh_token, refresh_expiry = await user_service.refresh_access_token(data.refresh_token)
    return RefreshTokenResponse(
        access_token=access_token,
        token_type=settings.TOKEN_TYPE,
        token_expiry=expiry,
        refresh_token=new_refresh_token,
        refresh_token_expiry=refresh_expiry,
    )

@user_routes.post("/logout",
                  summary="Logout and revoke refresh token",
                  response_description="Logged out successfully",
                  response_model=dict[str, str],
                  status_code=status.HTTP_200_OK)
async def logout(request: Request,
                 data: RefreshTokenRequest,
                 current_user: current_user_dependency,
                 user_service: user_service_dependency):
    await user_service.logout_user(data.refresh_token, user_id=current_user.id)
    return {"detail": "Logged out successfully"}

@user_routes.get("/me", response_model=CurrentUserInfo, status_code=status.HTTP_200_OK)
async def get_me(current_user: current_user_dependency):
    return current_user


# --------------------------Users (Admin & Self Protected)------------------------------------


@user_routes.get(
    "/users/{user_id}",
    summary="Get user by id",
    response_description="User data retrieved successfully",
    response_model=UserInfo,
    status_code=status.HTTP_200_OK)
async def get_user_by_user_id(user_id: UUID,
                              user_service: user_service_dependency,
                              auth_user: self_or_admin_dependency):
    user = await user_service.get_user_by_id(user_id=user_id)
    return user


@user_routes.get(
    "/users",
    summary="Get all users",
    response_description="List of all users retrieved successfully",
    response_model=list[UserInfo],
    status_code=status.HTTP_200_OK,
)
async def get_all_users(
    user_service: user_service_dependency,
    current_admin: admin_only_dependency,
    filters_query: Annotated[UsersFilterParams, Query()],
):
    users = await user_service.get_all_users(filters=filters_query)
    return users


@user_routes.patch(
    "/users/{user_id}",
    summary="Update user by ID",
    response_description="User updated successfully",
    response_model=UserInfo,
    status_code=status.HTTP_200_OK,
)
async def update_user_by_id(
    user_id: UUID,
    data: UserBasicUpdate,
    user_service: user_service_dependency,
    auth_user: self_or_admin_dependency,
):
    updated_user = await user_service.update_user_basic_info(
        user_id=user_id, update_data=data
    )
    return updated_user


@user_routes.delete(
    "/users/{user_id}",
    summary="Delete user by ID",
    response_description="User deleted successfully",
    response_model=dict[str, str],
    status_code=status.HTTP_200_OK,
)
async def delete_user_by_id(
    user_id: UUID,
    user_service: user_service_dependency,
    auth_user: self_or_admin_dependency,
):
    await user_service.delete_user_by_id(user_id=user_id)
    return {"detail": "User deleted successfully"}


# -------------------------AdminJS Schema-----------------------------------


@user_routes.get(
    "/admin/schema/users",
    summary="Get schema for AdminJS",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def get_user_schema_for_admin_js(current_admin: admin_only_dependency):
    return {"fields": User.get_admin_schema()}

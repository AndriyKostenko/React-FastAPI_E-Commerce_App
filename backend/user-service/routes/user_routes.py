from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, APIRouter, status, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.encoders import jsonable_encoder
from pydantic import EmailStr, Json
from sqlalchemy import JSON


from authentication import auth_manager
from schemas.user_schemas import (UserSignUp, 
                    UserInfo, 
                    TokenSchema, 
                    UserLoginDetails, 
                    CurrentUserInfo,
                    EmailSchema, 
                    EmailVerificationResponse, 
                    ForgotPasswordRequest, 
                    ForgotPasswordResponse,
                    ResetPasswordRequest,
                    PasswordUpdateResponse)
from dependencies.dependencies import user_crud_dependency
from service_layer.email_service import email_service
from shared.shared_instances import user_service_redis_manager, settings
from shared.customized_json_response import JSONResponse





user_routes = APIRouter(
    tags=["users"]
)

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

@user_routes.post('/register',
                  summary="Create new user",
                  response_description="New user created successfully",
                  response_model=UserInfo,
                  )
@user_service_redis_manager.ratelimiter(times=5, seconds=3600)  # Limit to 5 registrations per hour
async def create_user(request: Request,
                      data: UserSignUp,
                      background_tasks: BackgroundTasks,
                      user_service: user_crud_dependency
                      ):
    new_db_user = await user_service.create_user(data=data)
    # Send verification email in background
    await email_service.send_verification_email(
        email=new_db_user.email,
        user_id=new_db_user.id,
        user_role=new_db_user.role,
        background_tasks=background_tasks
    )
    return JSONResponse(content=new_db_user,
                        status_code=status.HTTP_201_CREATED)


@user_routes.post('/activate/{token}',
                 summary="Verify user email",
                 response_description="Email verified successfully",
                )
@user_service_redis_manager.cached(ttl=60)  # Cache for 1 minute
@user_service_redis_manager.ratelimiter(times=5, seconds=3600)  # Limit to 5 verifications per hour
async def verify_email(request: Request,
                       token: str,
                       user_service: user_crud_dependency):
    token_data = await auth_manager.get_current_user_from_token(token=token, required_purpose="email_verification")
    db_user = await user_service.update_user_verified_status(email=token_data.email, status=True)
    return JSONResponse(content=EmailVerificationResponse(
                                    detail="Email verified successfully",
                                    email=db_user.email,
                                    verified=db_user.is_verified
                                ),
                        status_code=status.HTTP_200_OK) 


@user_routes.post("/send-email",
                  summary="Send test verification email",)
@user_service_redis_manager.ratelimiter(times=3, seconds=3600)
async def simple_send(request: Request,
                      email: EmailSchema,
                      background_tasks: BackgroundTasks) -> JSONResponse:
    
    await email_service.send_verification_email(
        email=email.email,
        user_id="7066e133-fd23-4db8-b5c9-e12633a922d7",
        user_role="user",
        background_tasks=background_tasks
    )
    
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Email sent successfully"})


@user_routes.post("/login",
                  summary="User login",
                  response_model=UserLoginDetails,
                  response_description="User logged in successfully",)
@user_service_redis_manager.ratelimiter(times=5, seconds=60)  
async def login(request: Request,
                form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                user_service: user_crud_dependency): # request is reqired for rate limiting decorator
    # Authenticate user with credentials
    user = await auth_manager.get_authenticated_user(form_data=form_data, user_service=user_service)
    
    # updte last login might change user data, invalidating the redis cache
    await user_service_redis_manager.invalidate_cache(request=request)
    
    # creating access token
    access_token, expiry_timestamp = auth_manager.create_access_token(email=user.email,
                                                                      user_id=user.id, 
                                                                      role=user.role, 
                                                                      expires_delta=timedelta(minutes=settings.TIME_DELTA_MINUTES))
    return JSONResponse(
        content=UserLoginDetails(
            access_token=access_token,
            token_type=settings.TOKEN_TYPE,
            token_expiry=expiry_timestamp,
            user_id=user.id
            ),
        status_code=status.HTTP_200_OK
        )
    

@user_routes.post("/forgot-password",
                 summary="Request password reset email",
                 response_model=ForgotPasswordResponse
                 )
@user_service_redis_manager.ratelimiter(times=10, seconds=3600)  
async def request_password_reset(request: Request,
                                data: ForgotPasswordRequest,
                                background_tasks: BackgroundTasks,
                                user_service: user_crud_dependency):
    # Verify user exists
    user = await user_service.get_user_by_email(data.email)
    
    # Send password reset email
    await email_service.send_password_reset_email(
        email=user.email,
        user_id=user.id,
        user_role=user.role,
        background_tasks=background_tasks
    )
    
    return JSONResponse(
        content=ForgotPasswordResponse(
            detail="Password reset email sent",
            email=user.email
        ),
        status_code=status.HTTP_200_OK
    )
    
    
@user_routes.post("/password-reset/{token}",
                  summary="Reset password with token",
                  response_model=PasswordUpdateResponse,
                  response_description="Password reset successfully",
                  )
@user_service_redis_manager.ratelimiter(times=3, seconds=3600)  
async def reset_password(request: Request,
                        token: str,
                        data: ResetPasswordRequest,
                        background_tasks: BackgroundTasks,
                        user_service: user_crud_dependency):
    """Reset password using token"""
    token_data = await auth_manager.get_current_user_from_token(token=token, required_purpose="password_reset")
    
    await user_service.update_user_password(email=token_data.email, new_password=data.new_password)

    await user_service_redis_manager.invalidate_cache(request=request)  # Invalidate cache for user email

    await email_service.send_password_reset_success_email(
        email=token_data.email,
        template_body={
            "app_name": settings.MAIL_FROM_NAME,
            "email": token_data.email,
            "login_url": f"http://{settings.APP_HOST}:{settings.USER_SERVICE_APP_PORT}/login",
        },
        background_tasks=background_tasks   
    )
    
    return JSONResponse(
        content=PasswordUpdateResponse(
            detail="Password reset successfully",
            email=token_data.email
        ),
        status_code=status.HTTP_200_OK
    )



@user_routes.post("/token", 
                  response_model=TokenSchema,
                  response_description="New token generated successfully",
                  summary="Generate new access token for user",
                  )
@user_service_redis_manager.ratelimiter(times=5, seconds=60)  # same as login
@user_service_redis_manager.cached(ttl=60)  # Cache for 1 minute
async def generate_token(request: Request,
                        form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
                        user_service: user_crud_dependency):
    """Generate new token for user"""
    user = await auth_manager.get_authenticated_user(form_data=form_data, 
                                                    user_service=user_service)
    token, _ = auth_manager.create_access_token(email=user.email, 
                                                user_id=user.id, 
                                                role=user.role, 
                                                expires_delta=timedelta(minutes=settings.TIME_DELTA_MINUTES),
                                                purpose="access"
                                             )
    return JSONResponse(content=TokenSchema(access_token=token, 
                                            token_type=settings.TOKEN_TYPE),
                        status_code=status.HTTP_200_OK)


@user_routes.get("/me", 
                 response_model=CurrentUserInfo,
                 summary="Get current user data",
                 response_description="Current user data retrieved successfully",)
@user_service_redis_manager.cached(ttl=60) 
@user_service_redis_manager.ratelimiter(times=10, seconds=60)  # Limit to 10 requests per minute
async def get_current_user_data(request: Request,
                                current_user: Annotated[CurrentUserInfo, Depends(auth_manager.get_current_user_from_token)]):
    user = current_user
    return JSONResponse(content=user,
                        status_code=status.HTTP_200_OK)


@user_routes.get("/users/email/{user_email}",
                  summary="Get user by email",
                  response_description="User data retrieved successfully",
                  response_model=UserInfo
                  )
@user_service_redis_manager.cached(ttl=60) 
@user_service_redis_manager.ratelimiter(times=10, seconds=60)
async def get_user_by_email(request: Request,
                            user_email: EmailStr, 
                            user_service: user_crud_dependency):
    user = await user_service.get_user_by_email(user_email)
    return JSONResponse(content=user,
                        status_code=status.HTTP_200_OK)


@user_routes.get("/users/id/{user_id}",
                  summary="Get user by id",
                  response_description="User data retrieved successfully",
                  response_model=UserInfo
                  )
@user_service_redis_manager.cached(ttl=60) 
@user_service_redis_manager.ratelimiter(times=10, seconds=60) 
async def get_user_by_user_id(request: Request,
                              user_id: UUID, 
                              user_service: user_crud_dependency):
    user = await user_service.get_user_by_id(user_id=user_id)
    return JSONResponse(content=user,
                        status_code=status.HTTP_200_OK)


@user_routes.get("/users",
                  summary="Get all users",
                  response_description="List of all users retrieved successfully",
                  response_model=list[UserInfo],
                  )
@user_service_redis_manager.cached(ttl=60) 
@user_service_redis_manager.ratelimiter(times=10, seconds=60)
async def get_all_users(request: Request,
                        user_service: user_crud_dependency):
    users = await user_service.get_all_users()
    return JSONResponse(content=users,
                        status_code=status.HTTP_200_OK)




from datetime import timedelta, datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, APIRouter, status, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr


from authentication import auth_manager
from schemas import (UserSignUp, 
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
from services.user_service import UserCRUDService
from dependencies import get_user_service
from services.email_service import email_service
from utils.cache_response import cache_manager
from utils.rate_limiter import ratelimiter
from config import get_settings

user_routes = APIRouter(
    tags=["users"]
)
settings = get_settings()



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
    
4. Using `cache_response` decorator to cache GET responses.
    - cache responses using aio Redis for mproving performance
    - GET endpoints: Use both caching and rate limiting
    - cache key should be unique per user, e.g. by email or user ID
    - Use `invalidate_cache` to clear cache when user data changes.
    
5. All potential exceptions are handleled in 
the service layer, so no need to handle them here.
6. All data returned according to response_model schemas.
"""

@user_routes.post('/register',
                  summary="Create new user",
                  status_code=status.HTTP_201_CREATED,
                  response_model=UserInfo,
                  response_description="New user created successfully",
                  )
@ratelimiter(times=5, seconds=3600)  # Limit to 5 registrations per hour
async def create_user(request: Request,
                      user: UserSignUp,
                      background_tasks: BackgroundTasks,
                      user_crud_service: UserCRUDService = Depends(get_user_service)
                      ) -> UserInfo:
    new_db_user = await user_crud_service.create_user(user=user)
    
    # Send verification email in background
    await email_service.send_verification_email(
        email=new_db_user.email,
        user_id=str(new_db_user.id),
        user_role=new_db_user.role,
        background_tasks=background_tasks
    )

    return new_db_user


@user_routes.post("/send-email",
                  summary="Send verification email",
                  status_code=status.HTTP_200_OK,)
@ratelimiter(times=3, seconds=3600)
async def simple_send(request: Request,
                      email: EmailSchema,
                      background_tasks: BackgroundTasks) -> JSONResponse:
    
    await email_service.send_verification_email(
        email=email.email,
        user_id="test_id",
        user_role="user",
        background_tasks=background_tasks
    )
    
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Email sent successfully"})


@user_routes.post("/login",
                  summary="User login",
                  status_code=status.HTTP_200_OK,
                  response_model=UserLoginDetails,
                  response_description="User logged in successfully",)
@ratelimiter(times=5, seconds=60)  
async def login(request: Request,
                form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                user_service: UserCRUDService = Depends(get_user_service)) -> UserLoginDetails: # request is reqired for rate limiting decorator
    # Authenticate user with credentials
    user = await auth_manager.get_authenticated_user(form_data=form_data, user_service=user_service)
    
    # updte last login might change user data, invalidating the redis cache
    await cache_manager.invalidate_cache(namespace="users", key=user.email)
    
    # creating access token
    access_token, expiry_timestamp = auth_manager.create_access_token(email=user.email,
                                                                      user_id=user.id, 
                                                                      role=user.user_role, 
                                                                      expires_delta=timedelta(minutes=settings.TIME_DELTA_MINUTES))
   
    
    return UserLoginDetails(access_token=access_token,
                            token_type=settings.TOKEN_TYPE,
                            token_expiry=expiry_timestamp,
                            user_id=user.id)
    

@user_routes.post("/forgot-password",
                 summary="Request password reset email",
                 status_code=status.HTTP_200_OK,
                 response_model=ForgotPasswordResponse,
                 responses={
                     200: {"description": "Password reset email sent"},
                     404: {"description": "User not found"},
                 })
@ratelimiter(times=10, seconds=3600)  
async def request_password_reset(request: Request,
                                data: ForgotPasswordRequest,
                                background_tasks: BackgroundTasks,
                                user_crud_service: UserCRUDService = Depends(get_user_service)):
    # Verify user exists
    user = await user_crud_service.get_user_by_email(data.email)
    
    # Send password reset email
    await email_service.send_password_reset_email(
        email=user.email,
        user_id=user.id,
        user_role=user.role,
        background_tasks=background_tasks
    )
    
    return ForgotPasswordResponse(
        detail="Password reset email sent",
        email=user.email
    )
    
    
@user_routes.post("/password-reset/{token}",
                  summary="Reset password with token",
                  status_code=status.HTTP_200_OK,
                  response_model=PasswordUpdateResponse,
                  response_description="Password reset successfully",
                  )
@ratelimiter(times=3, seconds=3600)  
async def reset_password(request: Request,
                        token: str,
                        data: ResetPasswordRequest,
                        background_tasks: BackgroundTasks,
                        user_crud_service: UserCRUDService = Depends(get_user_service)) -> PasswordUpdateResponse:
    """Reset password using token"""
    token_data = await auth_manager.get_current_user_from_token(token=token, required_purpose="password_reset")
    
    await user_crud_service.update_user_password(user_email=token_data.email, new_password=data.new_password)
    
    await cache_manager.invalidate_cache(namespace="users", key=token_data.email)  # Invalidate cache for user email
    
    await email_service.send_password_reset_success_email(
        email=token_data.email,
        template_body={
            "app_name": settings.MAIL_FROM_NAME,
            "email": token_data.email,
            "login_url": f"http://{settings.APP_HOST}:{settings.APP_PORT}/login",
        },
        background_tasks=background_tasks   
    )
    
    return PasswordUpdateResponse(
        detail="Password reset successfully",
        email=token_data.email
    )


@user_routes.post("/token", 
                  response_model=TokenSchema,
                  response_description="New token generated successfully",
                  status_code=status.HTTP_200_OK,
                  )
@ratelimiter(times=5, seconds=60)  # same as login
async def generate_token(request: Request,
                        form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
                        user_service: UserCRUDService = Depends(get_user_service)) -> TokenSchema:
    """Generate new token for user"""
    user = await auth_manager.get_authenticated_user(form_data=form_data, user_service=user_service)
    # Check if user is verified
    token = auth_manager.create_access_token(user.email, 
                                             user.id, 
                                             user.role, 
                                             timedelta(minutes=settings.TIME_DELTA_MINUTES),
                                             )
    return TokenSchema(access_token=token, token_type=settings.TOKEN_TYPE)


@user_routes.get("/me", 
                 response_model=CurrentUserInfo,
                 status_code=status.HTTP_200_OK,
                 response_description="Current user data retrieved successfully",)
@ratelimiter(times=10, seconds=60)  # Limit to 10 requests per minute
@cache_manager.cached(namespace="users", key="current_user", ttl=60) # key should match parameter name
async def get_current_user_data(request: Request,
                                current_user: Annotated[CurrentUserInfo, Depends(auth_manager.get_current_user_from_token)]) -> CurrentUserInfo:
    return current_user


@user_routes.get("/user/email/{user_email}",
                  summary="Get user by email",
                  response_model=UserInfo,
                  response_description="User data retrieved successfully"
                  )
@ratelimiter(times=10, seconds=60)
@cache_manager.cached(namespace="users", key="user_email", ttl=60) # key should match parameter name
async def get_user_by_email(request: Request,
                            user_email: EmailStr, 
                            user_crud_service: UserCRUDService = Depends(get_user_service)) -> UserInfo:
    return await user_crud_service.get_user_by_email(user_email)


@user_routes.get("/user/id/{user_id}",
                  summary="Get user by id",
                  response_model=UserInfo,
                  response_description="User data retrieved successfully",
                  status_code=status.HTTP_200_OK
                  )
@ratelimiter(times=10, seconds=60)  
@cache_manager.cached(namespace="users", key="user_id", ttl=60) # key should match parameter name
async def get_user_by_user_id(request: Request,
                              user_id: UUID, 
                              user_crud_service: UserCRUDService = Depends(get_user_service)) -> UserInfo:
    return await user_crud_service.get_user_by_id(user_id=user_id)


@user_routes.get('/activate/{token}',
                 summary="Verify user email",
                 response_model=EmailVerificationResponse,
                 status_code=status.HTTP_200_OK,
                 response_description="Email verified successfully",
                )
@ratelimiter(times=5, seconds=3600)  # Limit to 5 verifications per hour
@cache_manager.cached(namespace="users", key="token", ttl=60)  # Cache for 1 minute
async def verify_email(request: Request,
                       token: str,
                       user_crud_service: UserCRUDService = Depends(get_user_service)) -> EmailVerificationResponse:
    token_data = await auth_manager.get_current_user_from_token(token=token, required_purpose="email_verification")
    db_user = await user_crud_service.update_user_verified_status(user_email=token_data.email)
    return EmailVerificationResponse(
        detail="Email verified successfully",
        email=db_user.email,
        verified=db_user.is_verified
    )


from datetime import timedelta
from typing import Annotated

from fastapi import Depends, APIRouter, status, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.security.authentication import auth_manager
from src.config import settings
from src.dependencies.dependencies import get_db_session
from src.schemas.user_schemas import (UserSignUp, 
                                      UserInfo, 
                                      TokenSchema, 
                                      UserLoginDetails, 
                                      CurrentUserInfo
                                      )
from src.schemas.email_schemas import (EmailSchema, 
                                       EmailVerificationResponse, 
                                       ForgotPasswordRequest, 
                                       ForgotPasswordResponse,
                                       ResetPasswordRequest
                                        )
from src.schemas.user_schemas import PasswordUpdateResponse
from src.service.user_service import UserCRUDService
from src.dependencies.dependencies import get_user_service
from src.service.email_service import email_service


user_routes = APIRouter(
    tags=["users"]
)


# registering new user...response_model will return the neccesary data...
# validation errors will be handeled automatically by pydantic and fastapi and sent 422
@user_routes.post('/register',
                  summary="Create new user",
                  status_code=status.HTTP_201_CREATED,
                  response_model=UserInfo,
                  response_description="New user created successfully",
                  responses={
                        409: {"description": "User already exists"},
                        201: {"description": "New user created successfully"},
                        500: {"description": "Internal server error"},
                        422: {"description": "Validation error"}
                        
                  })
async def create_user(user: UserSignUp,
                      background_tasks: BackgroundTasks,
                      user_crud_service: UserCRUDService = Depends(get_user_service)
                      ) -> UserInfo:
    #  create user in db with verified = False flag
    new_db_user = await user_crud_service.create_user(user=user)
    
    # Send verification email in background
    await email_service.send_verification_email(
        email=new_db_user.email,
        user_id=new_db_user.id,
        user_role=new_db_user.role,
        background_tasks=background_tasks
    )

    return new_db_user

@user_routes.post("/send-email")
async def simple_send(email: EmailSchema,
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
                  response_description="User logged in successfully",
                  responses={
                      401: {"description": "Could not validate user"},
                      200: {"description": "User logged in successfully"}
                  })
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                session: AsyncSession = Depends(get_db_session)) -> UserLoginDetails:
    user = await auth_manager.get_authenticated_user(form_data=form_data, session=session)
 
    # create access token
    access_token = auth_manager.create_access_token(user.email, 
                                                    user.id, 
                                                    user.role, 
                                                    timedelta(minutes=settings.TIME_DELTA_MINUTES))
    # get token expiry
    token_data = await auth_manager.get_current_user(access_token)
    
    return UserLoginDetails(token=access_token,
                            token_type=settings.TOKEN_TYPE,
                            token_expiry=token_data.exp,
                            user_id=user.id)
    

    
    
@user_routes.get('/activate/{token}',
                 summary="Verify user email",
                 response_model=EmailVerificationResponse,
                 status_code=status.HTTP_200_OK,
                 response_description="Email verified successfully",
                 responses={
                     200: {
                         "description": "Email verified successfully",
                         "content": {
                             "application/json": {
                                 "example": {
                                     "detail": "Email verified successfully",
                                     "email": "user@example.com",
                                     "verified": True
                                 }
                             }
                         }
                     },
                     401: {"detail": "User is not verified due to: Not enough segments"},
                     401: {"detail": "User is not verified due to: Signature has expired"},
                    })
                 
async def verify_email(token: str,
                       user_crud_service: UserCRUDService = Depends(get_user_service)) -> EmailVerificationResponse:
    token_data = await auth_manager.get_current_user(token=token, required_purpose="email_verification")
    await user_crud_service.update_user_verified_status(user_email=token_data.email, verified=True)
    return EmailVerificationResponse(
        detail="Email verified successfully",
        email=token_data.email,
        verified=True
    )


@user_routes.post("/forgot-password",
                 summary="Request password reset email",
                 status_code=status.HTTP_200_OK,
                 response_model=ForgotPasswordResponse,
                 responses={
                     200: {"description": "Password reset email sent"},
                     404: {"description": "User not found"},
                 })
async def request_password_reset(data: ForgotPasswordRequest,
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
                  responses={
                      401: {"description": "Invalid or expired token"},
                      401: {"description": "User is not verified due to: Not enough segments"},
                      401: {"description": "User is not verified due to: Signature has expired"},
                      200: {"description": "Password reset successfully"}
                  })
async def reset_password(token: str,
                        data: ResetPasswordRequest,
                        user_crud_service: UserCRUDService = Depends(get_user_service)) -> PasswordUpdateResponse:
    """Reset password using token"""
    token_data = await auth_manager.get_current_user(token=token, required_purpose="password_reset")
    await user_crud_service.update_user_password(user_email=token_data.email, new_password=data.new_password)
    return PasswordUpdateResponse(
        detail="Password reset successfully",
        email=token_data.email
    )



@user_routes.post("/token", 
                  response_model=TokenSchema,
                  response_description="New token generated successfully",
                  responses={
                      401: {"description": "Could not validate user"},
                      200: {"description": "New token generated successfully"}
                  })
async def generate_token(required_purpose: str,
                         user: UserInfo = Depends(auth_manager.get_authenticated_user)) -> TokenSchema:
    """Generate new token for user"""
    token = auth_manager.create_access_token(user.email, 
                                             user.id, 
                                             user.role, 
                                             timedelta(minutes=settings.TIME_DELTA_MINUTES),
                                             purpose=required_purpose)
    return TokenSchema(token=token, 
                       token_type=settings.TOKEN_TYPE,
                       token_purpose=required_purpose
                       )


@user_routes.get("/me",
                  summary="Get current user data",
                  response_model=CurrentUserInfo,
                  response_description="Current user data retrieved successfully",
                  responses={
                      401: {"description": "Unauthorized"},
                      200: {"description": "Current user data retrieved successfully"}
                  })
async def get_current_user_data(current_user: Annotated[dict, Depends(auth_manager.get_current_user)]) -> CurrentUserInfo:
    return current_user


@user_routes.get("/user/{user_email}",
                  summary="Get user by email",
                  response_model=UserInfo,
                  response_description="User data retrieved successfully",
                  responses={
                      404: {"description": "User not found"},
                      200: {"description": "User data retrieved successfully"}
                  })
async def get_user_by_email(user_email: str, 
                            user_crud_service: UserCRUDService = Depends(get_user_service)) -> UserInfo:
    return await user_crud_service.get_user_by_email(user_email)


@user_routes.post("/user/{id}",
                  summary="Get user by id",
                  response_model=UserInfo,
                  response_description="User data retrieved successfully",
                  responses={
                      404: {"description": "User not found"},
                      200: {"description": "User data retrieved successfully"}
                  })
async def get_user_by_user_id(id: str, 
                              user_crud_service: UserCRUDService = Depends(get_user_service)) -> UserInfo:
    return await user_crud_service.get_user_by_id(user_id=id)

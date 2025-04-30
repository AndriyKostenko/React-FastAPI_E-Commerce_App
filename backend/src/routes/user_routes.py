from datetime import timedelta
from typing import Annotated

from fastapi import Depends, APIRouter, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession


from src.security.authentication import auth_manager
from src.config import settings
from src.db.db_setup import get_db_session
from src.schemas.user_schemas import (UserSignUp, 
                                      UserInfo, 
                                      TokenSchema, 
                                      UserLoginDetails, 
                                      CurrentUserInfo, 
                                      EmailSchema)
from src.service.user_service import UserCRUDService
from src.dependencies.user_dependencies import get_user_service
from src.service.email import email_service


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
    
    # generating verification token
    verification_token = auth_manager.create_access_token(
        email=user.email,
        user_id="", # no user id yet
        role='user',
        expires_delta=timedelta(minutes=settings.VERIFICATION_TOKEN_EXPIRY_MINUTES)
    )
    
    # creating activation url
    activate_url = f"{settings.APP_HOST}:{settings.APP_PORT}/activate/{verification_token}"
    
    
    email_data = {
        "app_name": settings.MAIL_FROM_NAME,
        "email": user.email,
        "activate_url": activate_url
    }
    
    # Send account verification email
    await email_service.send_email(
        recipients=[user.email],
        subject="Verification of Email address",
        template_name="verify_email.html",
        context=email_data,
        background_tasks=background_tasks
    )
    
    #  create user in db with verified = False flag
    new_db_user = await user_crud_service.create_user(user=user)

    return new_db_user


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
    
    return UserLoginDetails(access_token=access_token,
                            token_type=settings.TOKEN_TYPE,
                            user_role=user.role,
                            token_expiry=token_data.exp,
                            user_id=user.id)
    
@user_routes.post('/send-email',)
async def send_verification_email(emails: EmailSchema, 
                                  background_tasks: BackgroundTasks,
                                  user_crud_service: UserCRUDService = Depends(get_user_service)):
    emails = emails.addresses
    email_service.create_message(
        recipients=emails,
        subject="Verification of Email address",
        template_name="verify_email.html",
        context={"app_name": settings.MAIL_FROM_NAME},
        background_tasks=background_tasks
    )
    
    
@user_routes.get('/activate/{token}',
                 summary="Verify user email",
                 status_code=status.HTTP_200_OK,
                 response_description="Email verified successfully")
async def verify_email(
    token: str,
    user_crud_service: UserCRUDService = Depends(get_user_service)
):
    # Verify token and get user email
    token_data = await auth_manager.get_current_user(token)

    # Update user verification status
    user = await user_crud_service.get_user_by_email(token_data['email'])
    
    # Update user's verified status
    await user_crud_service.update_user_verification(user.id, verified=True)

    return {"message": f"Email: {token_data['email']} verified successfully"}


    
    
@user_routes.post("/password-reset-request",
                  summary="Request password reset",
                  status_code=status.HTTP_200_OK,
                  response_description="Password reset request sent successfully",
                  responses={
                      404: {"description": "User not found"},
                      200: {"description": "Password reset request sent successfully"}
                  })
async def request_password_reset(email: str,
                                background_tasks: BackgroundTasks, 
                                user_crud_service: UserCRUDService = Depends(get_user_service)):
    user = await user_crud_service.get_user_by_email(email=email)
    
    # generate reset token
    reset_token = auth_manager.create_access_token(
        email=user.email,
        user_id=user.id,
        role=user.role,
        expires_delta=timedelta(minutes=settings.RESET_TOKEN_EXPIRY_MINUTES)
    )
    
    forget_password_url = f"{settings.APP_HOST}:{settings.APP_PORT}/password-reset/{reset_token}"
    
    email_data = {
        "app_name": settings.MAIL_FROM_NAME,
        "email": user.email,
        "forget_password_url": forget_password_url
    }
  
    # Send password reset email
    await email_service.send_email(
        recipients=[user.email],
        subject="Password Reset Request",
        template_name="password_reset.html", # Use your password reset template name
        context=email_data,
        background_tasks=background_tasks # Pass background_tasks
    )
    
    return {"message": f"Password reset instructions sent to email: {email}"}

@user_routes.post("/password-reset/{token}",
                  summary="Reset password with token",
                  status_code=status.HTTP_200_OK,
                  response_description="Password reset successfully",
                  responses={
                      401: {"description": "Invalid or expired token"},
                      200: {"description": "Password reset successfully"}
                  })
async def reset_password(token: str,
                        new_password: str,
                        user_crud_service: UserCRUDService = Depends(get_user_service)):
    """Reset password using token"""
    # verify token
    user = await auth_manager.get_current_user(token=token)

    # update password
    # Here you would typically hash the new password before saving it
    await user_crud_service.update_user_password(user_id=user.id, new_password=new_password)
    return {"message": "Password reset successfully"}



@user_routes.post("/token", 
                  response_model=TokenSchema,
                  response_description="New token generated successfully",
                  responses={
                      401: {"description": "Could not validate user"},
                      200: {"description": "New token generated successfully"}
                  })
async def generate_token(user: UserInfo = Depends(auth_manager.get_authenticated_user)) -> TokenSchema:
    token = auth_manager.create_access_token(user.email, 
                                             user.id, 
                                             user.role, 
                                             timedelta(minutes=settings.TIME_DELTA_MINUTES))
    return TokenSchema(access_token=token, token_type=settings.TOKEN_TYPE)


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

from fastapi import APIRouter, status, BackgroundTasks, Request

from fastapi.responses import JSONResponse
from uuid import UUID

from pydantic import EmailStr
from shared.shared_instances import notification_service_redis_manager
from shared.email_service import email_service
from schemas.notifications_schemas import EmailSchema, ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest, PasswordUpdateResponse
from shared.shared_instances import settings


notification_routes = APIRouter(tags=["notification-service"])


@notification_routes.post("/send-verification-email",
                         summary="Send verification email")
@notification_service_redis_manager.ratelimiter(times=3, seconds=3600)
async def send_verification_email(request: Request,
                                  user_email: EmailStr,
                                  user_id: UUID,
                                  user_token: str,
                                  user_role: str) -> JSONResponse:
    """Send verification email directly (for testing or admin purposes)"""
    await email_service.send_verification_email(
        email=user_email,
        user_id=user_id,
        user_role=user_role,
        token=user_token
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"message": "Verification email sent successfully"}
    )
        

@notification_routes.post("/send-forgot-password-request",
                 summary="Request password reset email",
                 response_model=ForgotPasswordResponse
                 )
@notification_service_redis_manager.ratelimiter(times=10, seconds=3600)  
async def request_password_reset(request: Request,
                                 user_email: EmailStr,
                                 user_id: UUID,
                                 user_token: str,
                                 user_role: str):
    """Send password reset email directly (for testing or admin purposes)"""

    await email_service.send_password_reset_email(
        email=user_email,
        user_id=user_id,
        user_role=user_role,
        reset_token=user_token
    )
    return JSONResponse(
        content=ForgotPasswordResponse(
            detail="Password reset email sent",
            email=user_email
        ),
        status_code=status.HTTP_200_OK
    )
    
    
@notification_routes.post("/send-password-reset-success-email",
                         summary="Send password reset success confirmation")
@notification_service_redis_manager.ratelimiter(times=3, seconds=3600)
async def send_password_reset_success_email(request: Request,
                                            user_email: EmailStr,
                                            ) -> JSONResponse:
    """Send password reset success confirmation email"""
    await email_service.send_password_reset_success_email(
        email=user_email,
        template_body={
            "app_name": settings.MAIL_FROM_NAME,
            "email": user_email,
            "login_url": f"http://{settings.APP_HOST}:{settings.USER_SERVICE_APP_PORT}/login",
        }
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Password reset success email sent"}
    )
        

@notification_routes.post("/send-welcome-email",
                         summary="Send welcome email")
@notification_service_redis_manager.ratelimiter(times=3, seconds=3600)
async def send_welcome_email(request: Request,
                            user_email: EmailStr,
                            user_name: str) -> JSONResponse:
    """Send welcome email to new users"""
    await email_service.send_welcome_email(
        email=user_email,
        user_name=user_name or user_email.split('@')[0],
        template_body={
            "app_name": settings.MAIL_FROM_NAME,
            "email": user_email,
            "user_name": user_name or user_email.split('@')[0]
        }
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Welcome email sent successfully"}
    )
        



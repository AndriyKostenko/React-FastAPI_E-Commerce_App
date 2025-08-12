from fastapi import Depends, APIRouter, status, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from uuid import UUID
from shared.shared_instances import notification_service_redis_manager
from service_layer.email_service import email_service
from schemas.notifications_schemas import EmailSchema, ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest, PasswordUpdateResponse


notification_routes = APIRouter(tags=["notification-service"])


@notification_routes.post("/send-verification-email",
                  summary="Send test verification email",)
@notification_service_redis_manager.ratelimiter(times=3, seconds=3600)
async def send_verification_email(request: Request,
                                  email: EmailSchema,
                                  user_id: UUID,
                                  background_tasks: BackgroundTasks) -> JSONResponse:
    
    await email_service.send_verification_email(
        email=email.email,
        user_id=user_id,
        user_role="user",
        background_tasks=background_tasks
    )
    
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Email sent successfully"})


@notification_routes.post("/send-forgot-password-request",
                 summary="Request password reset email",
                 response_model=ForgotPasswordResponse
                 )
@notification_service_redis_manager.ratelimiter(times=10, seconds=3600)  
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
    
@notification_routes.post("/send-password-reset-success-email",)
async def send_password_reset_success_email(request: Request,
                                           email: EmailSchema,
                                           background_tasks: BackgroundTasks) -> JSONResponse:

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


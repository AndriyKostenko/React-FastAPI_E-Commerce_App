from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from typing import List, Dict, Any
from src.config import settings
from src.errors.email_service_errors import EmailServiceError
from src.security.authentication import auth_manager
from datetime import timedelta


class EmailService:
    def __init__(self):
        self.fast_mail = FastMail(ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=settings.MAIL_PASSWORD,
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
            MAIL_STARTTLS=settings.MAIL_STARTTLS,
            MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
            USE_CREDENTIALS=settings.USE_CREDENTIALS,
            MAIL_DEBUG=settings.MAIL_DEBUG,
            TEMPLATE_FOLDER=settings.TEMPLATES_DIR,
            VALIDATE_CERTS=settings.VALIDATE_CERTS
        ))

    def create_message(self,
                       recipients: List[str],
                       subject: str,
                       template_body: Dict[str, Any]) -> MessageSchema:
        if not recipients:
            raise EmailServiceError("No recipients provided")

        return MessageSchema(
            subject=subject,
            recipients=recipients,
            template_body=template_body,
            subtype=MessageType.html
        )

    async def send_email(self,
                         recipients: List[str],
                         subject: str,
                         template_name: str,
                         template_body: Dict[str, Any]) -> None:
        message = self.create_message(recipients, subject, template_body)
        await self.fast_mail.send_message(message, template_name=template_name)

    async def send_verification_email(self,
                                      email: str,
                                      user_id: str,
                                      user_role: str,
                                      template_body: Dict[str, Any],
                                      background_tasks) -> None:
        token = auth_manager.create_access_token(
            email=email,
            user_id=user_id,
            role=user_role,
            expires_delta=timedelta(minutes=settings.VERIFICATION_TOKEN_EXPIRY_MINUTES)
        )

        activate_url = f"{settings.APP_HOST}:{settings.APP_PORT}/activate/{token}"
        email_data = {
            "app_name": settings.MAIL_FROM_NAME,
            "email": email,
            "activate_url": activate_url
        }

        background_tasks.add_task(
            self.send_email,
            email,
            "Email Verification",
            "email/email_verification.html",  # relative to TEMPLATE_FOLDER
            email_data
        )
        
    async def send_password_reset_email(self,
                                        email: str,
                                        user_id: str,
                                        user_role: str,
                                        background_tasks) -> None:
            token = auth_manager.create_access_token(
                email=email,
                user_id=user_id,
                role=user_role,
                expires_delta=timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRY_MINUTES)
            )
    
            reset_url = f"{settings.APP_HOST}:{settings.APP_PORT}/reset-password/{token}"
            email_data = {
                "app_name": settings.MAIL_FROM_NAME,
                "email": email,
                "reset_url": reset_url
            }
    
            background_tasks.add_task(
                self.send_email,
                [email],
                "Password Reset",
                email_data
            )
            
email_service = EmailService()

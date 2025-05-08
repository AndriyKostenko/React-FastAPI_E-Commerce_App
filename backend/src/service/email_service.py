import logging

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import ValidationError
from typing import List, Dict, Any
from src.config import settings
from src.errors.email_service_errors import EmailServiceError
from src.security.authentication import auth_manager
from datetime import timedelta



logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.config = ConnectionConfig(
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
        )
        self.fast_mail = FastMail(self.config)

    def create_message(self,
                       recipients: List[str],
                       subject: str,
                       template_body: Dict[str, str]) -> MessageSchema:
        if not recipients:
            logger.error("No recipients provided during creation of email message")
            raise EmailServiceError("No recipients provided")
        
        try:
            return MessageSchema(
                subject=subject,
                recipients=recipients,
                template_body=template_body,
                subtype=MessageType.html
            )
        except ValidationError as e:
            logger.error(f"Validation error while creating email message: {e}")
            raise EmailServiceError("Validation error while creating email message")

    async def _send_email_async(self,
                                recipients: List[str],
                                subject: str,
                                template_name: str,
                                template_body: Dict[str, str]) -> None:
        try:
            message = self.create_message(recipients, subject, template_body)
            await self.fast_mail.send_message(message, template_name=template_name)
        except ConnectionErrors as e:
            logger.error(f"Connection error while sending email: {e}")
            raise EmailServiceError("Connection error while sending email")
        
    def send_email_background(self,
                              background_tasks,
                              subject: str,
                              template_body: Dict[str, str],
                              recipients: List[str],
                              temaplate_name: str) -> None:
        """Send email in the background using FastAPI background tasks.
        FastAPI's BackgroundTasks runs after the response is returned, 
        but it's not a separate thread or process—it just schedules the 
        function to run in the same event loop.
        FastAPI will await it behind the scenes during its lifecycle.
        """
        background_tasks.add_task(
            self._send_email_async,
            subject=subject,
            recipients=recipients,
            template_name=temaplate_name,
            template_body=template_body
        )

    async def send_verification_email(self,
                                      email: str,
                                      user_id: str,
                                      user_role: str,
                                      background_tasks) -> None:
        if not email or not user_id or not user_role:
            logger.error("Email, user_id, or user_role is missing")
            raise EmailServiceError("Email, user_id, or user_role is missing")

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

        self.send_email_background(
            background_tasks=background_tasks,
            subject="Email Verification",
            template_body=email_data,
            recipients=[email],
            temaplate_name="email/email_verification.html"
        )
        
    async def send_password_reset_email(self,
                                        email: str,
                                        user_id: str,
                                        user_role: str,
                                        background_tasks) -> None:
            ...
            
email_service = EmailService()

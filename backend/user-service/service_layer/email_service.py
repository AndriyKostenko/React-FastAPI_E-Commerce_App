from datetime import timedelta
from typing import List, Dict
from uuid import UUID

from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import ValidationError, EmailStr
from jinja2 import Environment, FileSystemLoader, TemplateNotFound


from errors.errors import EmailServiceError
from authentication import auth_manager
from shared.shared_instances import settings, logger



class EmailService:
    """Service for sending emails using FastAPI Mail and Jinja2 templates."""
    
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.config = ConnectionConfig(
            MAIL_USERNAME=self.settings.MAIL_USERNAME,
            MAIL_PASSWORD=self.settings.MAIL_PASSWORD,
            MAIL_FROM=self.settings.MAIL_FROM,
            MAIL_PORT=self.settings.MAIL_PORT,
            MAIL_SERVER=self.settings.MAIL_SERVER,
            MAIL_FROM_NAME=self.settings.MAIL_FROM_NAME,
            MAIL_STARTTLS=self.settings.MAIL_STARTTLS,
            MAIL_SSL_TLS=self.settings.MAIL_SSL_TLS,
            USE_CREDENTIALS=self.settings.USE_CREDENTIALS,
            MAIL_DEBUG=self.settings.MAIL_DEBUG,
            TEMPLATE_FOLDER=self.settings.TEMPLATES_DIR,
            VALIDATE_CERTS=self.settings.VALIDATE_CERTS
        )
        self.jinja_env = Environment(loader=FileSystemLoader(self.config.TEMPLATE_FOLDER))
        self.fast_mail = FastMail(self.config)

    def render_template(self, template_name: str, template_body: Dict[str, str]) -> str:
        """Render a template with the given context."""
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**template_body)
        except TemplateNotFound:
            self.logger.error(f"Email template not found: {template_name}")
            raise EmailServiceError("Template not found")
        
    def create_message(self,
                       recipients: List[str],
                       subject: str,
                       rendered_html: str) -> MessageSchema:
        if not recipients:
            self.logger.error("No recipients provided during creation of email message")
            raise EmailServiceError("No recipients provided")
        
        try:
            return MessageSchema(
                subject=subject,
                recipients=recipients,
                body=rendered_html, # final HTML string
                subtype=MessageType.html
            )
        except ValidationError as e:
            self.logger.error(f"Validation error while creating email message: {e}")
            raise EmailServiceError("Validation error while creating email message")

    async def _send_email_async(self,
                                recipients: List[str],
                                subject: str,
                                template_name: str,
                                template_body: Dict[str, str]) -> None:
        try:
            rendered_html = self.render_template(template_name=template_name, template_body=template_body)
            message = self.create_message(recipients, subject, rendered_html)
            await self.fast_mail.send_message(message, template_name=template_name)
        except ConnectionErrors as e:
            self.logger.error(f"Connection error while sending email: {e}")
            raise EmailServiceError("Connection error while sending email")
        
    def send_email_background(self,
                              background_tasks: BackgroundTasks,
                              subject: str,
                              template_body: Dict[str, str | None],
                              recipients: List[str],
                              template_name: str) -> None:
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
            template_name=template_name,
            template_body=template_body
        )
    

    async def send_verification_email(self,
                                      email: EmailStr,
                                      user_id: UUID,
                                      user_role: str | None,
                                      background_tasks: BackgroundTasks) -> None:
        if not email or not user_id or not user_role:
            self.logger.error("Email, user_id, or user_role is missing")
            raise EmailServiceError("Email, user_id, or user_role is missing")

        # returns token and exparation time, needed only token
        token, _ = auth_manager.create_access_token(
            email=email,
            user_id=user_id,
            role=user_role,
            expires_delta=timedelta(minutes=self.settings.VERIFICATION_TOKEN_EXPIRY_MINUTES),
            purpose="email_verification"
        )

        activate_url = f"http://{self.settings.APP_HOST}:{self.settings.USER_SERVICE_APP_PORT}/api/v1/activate/{token}"

        self.logger.info(f"Sending verification email to: {email} with token: {token}")
        
        email_data: Dict[str, str | None] = {
            "app_name": self.settings.MAIL_FROM_NAME,
            "email": email,
            "activate_url": activate_url
        }

        self.send_email_background(
            background_tasks=background_tasks,
            subject="Email Verification",
            template_body=email_data,
            recipients=[email],
            template_name="email_verification.html"
        )
        
    async def send_password_reset_email(self,
                                        email: EmailStr,
                                        user_id: UUID,
                                        user_role: str | None,
                                        background_tasks: BackgroundTasks) -> None:
        
        if not email or not user_id or not user_role:
            self.logger.error("Email, user_id, or user_role is missing")
            raise EmailServiceError("Email, user_id, or user_role is missing")
        
        # returns token and exparation time, needed only token
        token, _ = auth_manager.create_access_token(
            email=email,
            user_id=user_id,
            role=user_role,
            expires_delta=timedelta(minutes=self.settings.RESET_TOKEN_EXPIRY_MINUTES),
            purpose="password_reset"
        )
        reset_url = f"http://{self.settings.APP_HOST}:{self.settings.USER_SERVICE_APP_PORT}/api/v1/password-reset/{token}"


        self.logger.info(f"Sending password reset email to {email} with token {token}")
        
        email_data = {
            "app_name": self.settings.MAIL_FROM_NAME,
            "email": email,
            "reset_url": reset_url,
            "expiry_minutes": self.settings.RESET_TOKEN_EXPIRY_MINUTES
        }

        
        self.send_email_background(
            background_tasks=background_tasks,
            subject="Password Reset",
            template_body=email_data,
            recipients=[email],
            template_name="password_reset.html"
        )
        
    async def send_password_reset_success_email(self,
                                        email: str,
                                        template_body: Dict[str, str | None],
                                        background_tasks: BackgroundTasks) -> None:
        if not email:
            self.logger.error("Email is missing")
            raise EmailServiceError("Email is missing")
        


        self.send_email_background(
            background_tasks=background_tasks,
            subject="Password Reset Successful",
            template_body=template_body,
            recipients=[email],
            template_name="password_reset_confirmation.html"
        )
            
email_service = EmailService(settings=settings, logger=logger)

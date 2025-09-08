from datetime import datetime
from typing import List, Dict
from uuid import UUID

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import ValidationError, EmailStr
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from shared.metaclasses import SingletonMetaClass
from shared.base_exceptions import EmailServiceError

class EmailService(metaclass=SingletonMetaClass):
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
        self.jinja_env = Environment(loader=FileSystemLoader(self.config.TEMPLATE_FOLDER)) # type: ignore
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
        """Create email message schema."""
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

    async def send_email_async(self,
                               recipients: List[str],
                               subject: str,
                               template_name: str,
                               template_body: Dict[str, str]) -> None:
        """Send email asynchronously - used directly by event consumers."""
        try:
            self.logger.info(f"Preparing to send email to {recipients} with subject: {subject}")
            
            rendered_html = self.render_template(template_name=template_name, template_body=template_body)
            message = self.create_message(recipients, subject, rendered_html)
            
            await self.fast_mail.send_message(message, template_name=template_name)
            
            self.logger.info(f"Email successfully sent to {recipients}")
            
        except ConnectionErrors as e:
            self.logger.error(f"Connection error while sending email: {e}")
            raise EmailServiceError("Connection error while sending email")
        except Exception as e:
            self.logger.error(f"Unexpected error while sending email: {e}")
            raise EmailServiceError(f"Failed to send email: {str(e)}")
           
    async def send_verification_email(self,
                                      email: EmailStr,
                                      user_id: UUID,
                                      user_role: str | None,
                                      token) -> None:
        """Send verification email - called from event consumer."""
        if not email or not user_id or not user_role:
            self.logger.error("Email, user_id, or user_role is missing")
            raise EmailServiceError("Email, user_id, or user_role is missing")


        activate_url = f"http://{self.settings.APP_HOST}:{self.settings.USER_SERVICE_APP_PORT}/api/v1/activate/{token}"

        self.logger.info(f"Sending verification email to: {email} with token: {token}")
        
        email_data: Dict[str, str] = {
            "app_name": self.settings.MAIL_FROM_NAME,
            "email": email,
            "activate_url": activate_url
        }

        await self.send_email_async(
            subject="Email Verification",
            template_body=email_data,
            recipients=[email],
            template_name="email_verification.html"
        )
        
    async def send_password_reset_email(self,
                                        email: EmailStr,
                                        user_id: UUID,
                                        user_role: str | None,
                                        reset_token) -> None:
        """Send password reset email - called from event consumer."""
        if not email or not user_id or not user_role:
            self.logger.error("Email, user_id, or user_role is missing")
            raise EmailServiceError("Email, user_id, or user_role is missing")
        
        reset_url = f"http://{self.settings.APP_HOST}:{self.settings.USER_SERVICE_APP_PORT}{self.settings.NOTIFICATION_SERVICE_URL_API_VERSION}/password-reset/{reset_token}"

        self.logger.info(f"Sending password reset email to: {email} with token: {reset_token}")
        
        email_data = {
            "app_name": self.settings.MAIL_FROM_NAME,
            "email": email,
            "reset_url": reset_url,
            "expiry_minutes": self.settings.RESET_TOKEN_EXPIRY_MINUTES
        }

        await self.send_email_async(
            subject="Password Reset Request",
            template_body=email_data,
            recipients=[email],
            template_name="password_reset.html"
        )
        
    async def send_password_reset_success_email(self,
                                        email: str,
                                        template_body: Dict[str, str]) -> None:
        """Send password reset confirmation email."""
        if not email:
            self.logger.error("Email is missing")
            raise EmailServiceError("Email is missing")

        self.logger.info(f"Sending password reset confirmation email to: {email}")
        
        await self.send_email_async(
            subject="Password Reset Successful",
            template_body=template_body,
            recipients=[email],
            template_name="password_reset_confirmation.html"
        )
        
    async def send_welcome_email(self,
                                 email: EmailStr,
                                 user_name: str,
                                 template_body: dict[str, str]):
        """Send welcome email to new users."""
        if not email:
            self.logger.error("Email is missing")
            raise EmailServiceError("Email is missing")

        self.logger.info(f"Sending welcome email to {email}")

        # Use provided template_body or create default
        email_data = template_body or {
            "app_name": self.settings.MAIL_FROM_NAME,
            "email": email,
            "user_name": user_name or email.split('@')[0]
        }

        await self.send_email_async(
            subject=f"Welcome to {self.settings.MAIL_FROM_NAME}!",
            template_body=email_data,
            recipients=[email],
            template_name="welcome.html"
        )
        
    async def send_login_notification_email(self,
                                           email: EmailStr,
                                           login_time: datetime
                                           ) -> None:
        """Send login notification email."""
        if not email:
            self.logger.error("Email is missing")
            raise EmailServiceError("Email is missing")

        self.logger.info(f"Sending login notification email to {email}")

        email_data = {
            "app_name": self.settings.MAIL_FROM_NAME,
            "email": email,
            "login_time": login_time
        }

        await self.send_email_async(
            subject="New Login to Your Account",
            template_body=email_data,
            recipients=[email],
            template_name="login_notification.html"
        )
       
            


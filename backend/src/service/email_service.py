from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi.background import BackgroundTasks
from datetime import timedelta
from typing import List, Dict, Any

from src.config import settings
from src.errors.email_service_errors import EmailServiceError
from src.security.authentication import auth_manager


class EmailService:
    # Initialize the email configuration
    conf = ConnectionConfig(
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
        TEMPLATE_FOLDER=settings.TEMPLATES_DIR
    )
    
    def __init__(self):
        self.fast_mail = FastMail(self.conf)
        
    async def send_email(self,
                         recipients: List[str],
                         subject: str,
                         template_name: str,
                         context: Dict[str, Any],
                         background_tasks: BackgroundTasks) -> None:
        """
        Send an email using a template.
        
        Args:
            recipients: List of email recipients
            subject: Email subject
            template_name: Name of the template file
            context: Dictionary with context variables for the template
            background_tasks: Background tasks to run the email sending
        """
        # Create the message schema
        message = MessageSchema(
            subject=subject,
            recipients=recipients,
            template_body=context,
            subtype=MessageType.html,
        )
            
        # Send the message in the background
        background_tasks.add_task(
            self.fast_mail.send_message,
            message,
            template_name=template_name
        )
    
    async def send_verification_email(self,
                                     email: str,
                                     user_id: str,
                                     user_role: str,
                                     background_tasks: BackgroundTasks) -> None:
        """
        Send verification email to a user
        
        Args:
            email: User's email address
            user_id: User's ID
            background_tasks: Background tasks runner
            auth_manager: Optional auth manager (imported at method level to avoid circular imports)
        """
            
        # Generate verification token with actual user ID
        verification_token = auth_manager.create_access_token(
            email=email,
            user_id=user_id,
            role=user_role,
            expires_delta=timedelta(minutes=settings.VERIFICATION_TOKEN_EXPIRY_MINUTES)
        )
        
        # Create activation URL
        activate_url = f"{settings.APP_HOST}:{settings.APP_PORT}/activate/{verification_token}"
        
        # Prepare email context data
        email_data = {
            "app_name": settings.MAIL_FROM_NAME,
            "email": email,
            "activate_url": activate_url
        }
        
        # Send verification email
        await self.send_email(
            recipients=[email],
            subject="Verification of Email address",
            template_name="verify_email.html",
            context=email_data,
            background_tasks=background_tasks
        )
        
    async def send_password_reset_email(self,
                                        email: str,
                                        user_id: str,
                                        user_role: str,
                                        background_tasks: BackgroundTasks
                                        ) -> None:
        """
        Send password reset email to a user
        
        Args:
            email: User's email address
            user_id: User's ID
            user_role: User's role
            background_tasks: Background tasks runner
            auth_manager: Optional auth manager (imported at method level to avoid circular imports)
        """
            
        # Generate reset token
        reset_token = auth_manager.create_access_token(
            email=email,
            user_id=user_id,
            role=user_role,
            expires_delta=timedelta(minutes=settings.RESET_TOKEN_EXPIRY_MINUTES)
        )
        
        # Create reset URL
        forget_password_url = f"{settings.APP_HOST}:{settings.APP_PORT}/password-reset/{reset_token}"
        
        # Prepare email context data
        email_data = {
            "app_name": settings.MAIL_FROM_NAME,
            "email": email,
            "forget_password_url": forget_password_url
        }
        
        # Send password reset email
        await self.send_email(
            recipients=[email],
            subject="Password Reset Request",
            template_name="password_reset.html",
            context=email_data,
            background_tasks=background_tasks
        )
        
# Create singleton instance
email_service = EmailService()
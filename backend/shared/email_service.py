from datetime import datetime
from logging import Logger
from typing import Any

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import ValidationError, EmailStr
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from shared.metaclasses import SingletonMetaClass
from shared.base_exceptions import EmailServiceError
from shared.settings import Settings
from shared.schemas.event_schemas import (
    UserRegisteredEvent,
    PasswordResetRequestedEvent,
    UserLoginEvent,
    PasswordResetSuccessEvent,
    OrderCreatedEvent,
    OrderConfirmedEvent,
    OrderCancelledEvent
)

class EmailService(metaclass=SingletonMetaClass):
    """Service for sending emails using FastAPI Mail and Jinja2 templates."""
    def __init__(self, settings: Settings, logger: Logger):
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

    def render_template(self, template_name: str, template_body: dict[str, str]) -> str:
        """Render a template with the given context."""
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**template_body)
        except TemplateNotFound:
            self.logger.error(f"Email template not found: {template_name}")
            raise EmailServiceError("Template not found")

    def create_message(self,
                       recipients: list[str],
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
                               recipients: list[str],
                               subject: str,
                               template_name: str,
                               template_body: dict[str, Any]) -> None:
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


class UserRelatedNotifications(EmailService):
    """Service for sending User specific notification emails (registration, password reset, login etc"""
    def __init__(self, settings: Settings, logger: Logger):
        super().__init__(settings, logger)

    async def send_verification_email(self, event: UserRegisteredEvent) -> None:
        """Send verification email - called from event consumer."""
        await self.send_email_async(
            subject="Email Verification",
            template_body={
                "app_name": self.settings.MAIL_FROM_NAME,
                "email": event.user_email,
                "activate_url": f"http://{self.settings.APP_HOST}:{self.settings.USER_SERVICE_APP_PORT}{self.settings.USER_SERVICE_URL_API_VERSION}/activate/{event.token}"
            },
            recipients=[event.user_email],
            template_name="email_verification.html"
        )
        self.logger.info(f"Sending verification email to: {event.user_email} with token: {event.token}")

    async def send_password_reset_email(self, event: PasswordResetRequestedEvent) -> None:
        """Send password reset email - called from event consumer."""
        await self.send_email_async(
            subject="Password Reset Request",
            template_body={
                "app_name": self.settings.MAIL_FROM_NAME,
                "email": event.user_email,
                "reset_url": f"http://{self.settings.APP_HOST}:{self.settings.USER_SERVICE_APP_PORT}{self.settings.NOTIFICATION_SERVICE_URL_API_VERSION}/password-reset/{event.reset_token}",
                "expiry_minutes": self.settings.RESET_TOKEN_EXPIRY_MINUTES
            },
            recipients=[event.user_email],
            template_name="password_reset.html"
        )
        self.logger.info(f"Sending password reset email to: {event.user_email} with token: {event.reset_token}")

    async def send_password_reset_success_email(self, event: PasswordResetSuccessEvent) -> None:
        """Send password reset confirmation email."""
        await self.send_email_async(
            subject="Password Reset Successful",
            template_body={
                "app_name": self.settings.MAIL_FROM_NAME,
                "email": event.user_email,
                "login_url": f"http://{self.settings.APP_HOST}:{self.settings.API_GATEWAY_SERVICE_APP_PORT}{self.settings.API_GATEWAY_SERVICE_URL_API_VERSION}/login"
            },
            recipients=[event.user_email],
            template_name="password_reset_confirmation.html"
        )
        self.logger.info(f"Sending password reset confirmation email to: {event.user_email}")

    async def send_login_notification_email(self, event: UserLoginEvent) -> None:
        """Send login notification email."""
        await self.send_email_async(
            subject="New Login to Your Account",
            template_body={
                "app_name": self.settings.MAIL_FROM_NAME,
                "email": event.user_email,
                "login_time": event.timestamp
            },
            recipients=[event.user_email],
            template_name="login_notification.html"
        )
        self.logger.info(f"Sending login notification email to {event.user_email}")


class OrderRelatedNotifications(EmailService):
    """Service for sending Order specific notification emails (order created, order cancelled etc"""
    def __init__(self, settings: Settings, logger: Logger):
        super().__init__(settings, logger)

    async def send_order_created_notification(self, event: OrderCreatedEvent) -> None:
        """
        Send notification when order is created (PENDING status).
        This is a "we received your order" notification.
        """
        await self.send_email_async(
            recipients=[event.user_email],
            subject="Order Received - Awaiting Confirmation",
            template_name="order_created.html",
            template_body={
                "order_id": str(event.order_id),
                "total_amount": float(event.total_amount),
                "items_count": len(event.items),
                "app_name": self.settings.MAIL_FROM_NAME,
                "order_url": f"http://{self.settings.APP_HOST}/orders/{event.order_id}"
            }
        )
        self.logger.info(f"Sent order created notification for order: {event.order_id}")

    async def send_order_confirmed_notification(self, event: OrderConfirmedEvent) -> None:
        """
        Send notification when order is confirmed (inventory reserved successfully).
        This is a "your order is confirmed" notification.
        """
        await self.send_email_async(
            recipients=[event.user_email],
            subject="Order Confirmed - Ready for Processing",
            template_name="order_confirmed.html",
            template_body={
                "order_id": str(event.order_id),
                "app_name": self.settings.MAIL_FROM_NAME,
                "order_url": f"http://{self.settings.APP_HOST}/orders/{event.order_id}",
                "tracking_url": f"http://{self.settings.APP_HOST}/orders/{event.order_id}/tracking"
            }
        )
        self.logger.info(f"Sent order confirmation for order: {event.order_id}")

    async def send_order_cancelled_notification(self, event: OrderCancelledEvent) -> None:
        """
        Send notification when order is cancelled (inventory not available or other issues).
        This is a "sorry, your order couldn't be processed" notification.
        """
        await self.send_email_async(
            recipients=[event.user_email],
            subject="Order Cancelled - Refund Initiated",
            template_name="order_cancelled.html",
            template_body={
                "order_id": str(event.order_id),
                "reason": event.reason,
                "app_name": self.settings.MAIL_FROM_NAME,
                "support_url": f"http://{self.settings.APP_HOST}/support",
                "contact_email": self.settings.MAIL_FROM
            }
        )
        self.logger.info(f"Sent order cancellation notification for order {event.order_id}")

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi import Depends
from src.config import settings
from fastapi.background import BackgroundTasks


class EmailService:
    # Initialize the email configuration
    # using FastAPI Mail's ConnectionConfig
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
    )
    
    def __init__(self):
        self.fast_mail = FastMail(self.conf)
        
    
    async def send_email(self, 
                         recipients: list, 
                         subject: str, 
                         context: dict, 
                         template_name: str,
                         background_tasks: BackgroundTasks) -> None:
        # Create a message schema
        # with the provided subject, recipients, and context
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
    
    
email_service = EmailService()
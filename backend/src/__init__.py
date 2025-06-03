import datetime
from typing import List, Dict
from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from fastapi.exceptions import ResponseValidationError, RequestValidationError

from src.db.db_setup import database_session_manager
from src.routes.admin_routes import admin_routes
from src.routes.category_routes import category_routes
from src.routes.payment_route import payment_routes
from src.routes.product_route import product_routes
from src.routes.review_routes import review_routes
from src.routes.user_routes import user_routes
from src.routes.orders_routes import order_routes
from src.errors.user_service_errors import (UserNotFoundError, 
                                            UserAlreadyExistsError, 
                                            UserServiceDatabaseError, 
                                            UserIsNotVerifiedError, 
                                            UserPasswordError, 
                                            UserEmailError, 
                                            UserCreationError, 
                                            UserValidationError, 
                                            UserUpdateError, 
                                            UserDeletionError, 
                                            UserAuthenticationError)
from src.errors.rate_limiter_error import RateLimitExceededError
from src.errors.database_errors import (DatabaseConnectionError,
                                        DatabaseSessionError)
from src.errors.email_service_errors import EmailServiceError
from src.utils.logger_config import setup_logger
from src.config import get_settings


# Configure logging
logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
   
    logger.info(f"Server has started at {datetime.datetime.now()}")
    
    # Use a boolean to track connection success
    db_initialized = False
    
    # Test if engine is initialized
    if database_session_manager.async_engine is not None:
        try:
            # Initialize the database
            await database_session_manager.init_db()
            db_initialized = True
            logger.info(f'Database initialized succesfully at {datetime.datetime.now()}')
        except DatabaseConnectionError as e:
            logger.error(f"Database connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
    
    if not db_initialized:
        logger.warning("Application started with database unavailable! Some features will not work.")
    
    yield
    
    # Cleanup
    if database_session_manager.is_connected:
        await database_session_manager.close()
    
    logger.info(f"Server has shut down at {datetime.datetime.now()}")



app = FastAPI(
    title="E-Commerce API",
    description="An API for user, products and orders for E-commerce",
    version="0.0.1",
    lifespan=lifespan
)

# adding the middleware to the app for handling different types of errors
def add_exception_handlers(app: FastAPI):
    """
    This function adds exception handlers to the FastAPI application.
    """
    # Custom Exception handlers for Pydantic validation errors in request and response
    @app.exception_handler(ValidationError)
    async def validation_input_exception_handler(request: Request, exc: ValidationError): # type: ignore
        errors: List[Dict[str, str | int]] = [{"field": err['loc'][0], "message": err['msg']} for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": 'Validation input error', "errors": errors}
        )
        
    # Custom Exception handlers for Pydantic validation errors in request and response
    @app.exception_handler(ResponseValidationError)
    async def validation_response_exception_handler(request: Request, exc: ResponseValidationError): # type: ignore
        errors: List[Dict[str, str | int]] = [{"field": err['loc'][0], "message": err['msg']} for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": 'Validation response error', "errors": errors}
        )

    # Custom Exception handlers for Pydantic validation errors in request and response
    @app.exception_handler(RequestValidationError)
    async def validation_request_exception_handler(request: Request, exc: RequestValidationError): # type: ignore
        errors: List[Dict[str, str | int]] = [{"field": err['loc'][0], "message": err['msg']} for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": 'Validation request error', "errors": errors}
        )
        
    # Custom Exception handlers for UserCRUDService errors    
    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(request: Request, exc: UserNotFoundError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)}
        )

    @app.exception_handler(UserAlreadyExistsError)
    async def user_exists_handler(request: Request, exc: UserAlreadyExistsError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserCreationError)
    async def user_creation_error_handler(request: Request, exc: UserCreationError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(UserValidationError)
    async def user_validation_error_handler(request: Request, exc: UserValidationError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserUpdateError)
    async def user_update_error_handler(request: Request, exc: UserUpdateError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserDeletionError)
    async def user_deletion_error_handler(request: Request, exc: UserDeletionError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserAuthenticationError)
    async def user_authentication_error_handler(request: Request, exc: UserAuthenticationError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserPasswordError)
    async def user_password_error_handler(request: Request, exc: UserPasswordError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserEmailError)
    async def user_email_error_handler(request: Request, exc: UserEmailError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserServiceDatabaseError)
    async def user_service_database_error_handler(request: Request, exc: UserServiceDatabaseError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserIsNotVerifiedError)
    async def user_is_not_verified_handler(request: Request, exc: UserIsNotVerifiedError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)}
        )
        
    # Custom Exception handlers for database errors
    @app.exception_handler(DatabaseConnectionError)
    async def database_connection_error_handler(request: Request, exc: DatabaseConnectionError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(DatabaseSessionError)
    async def database_session_error_handler(request: Request, exc: DatabaseSessionError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
        
    # Custom Exception handlers for email service errors
    @app.exception_handler(EmailServiceError)
    async def email_service_error_handler(request: Request, exc: EmailServiceError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
        
    # Custom Exception handlers for rate limit exceeded errors
    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_handler(request: Request, exc: RateLimitExceededError): # type: ignore
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": str(exc)}
        )

        
        

    
        

# adding exception handlers to the app      
add_exception_handlers(app)
        


# CORS or "Cross-Origin Resource Sharing" is a mechanism that 
# allows restricted resources on a web page to be requested from another domain 
# outside the domain from which the first resource was served.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().CORS_ALLOWED_ORIGINS,
    allow_credentials=get_settings().CORS_ALLOW_CREDENTIALS,
    allow_methods=get_settings().CORS_ALLOWED_METHODS,
    allow_headers=get_settings().CORS_ALLOWED_HEADERS,
)

# Static files configuration
app.mount("/media", StaticFiles(directory="media"), name="media")

# including all the routers to the app
app.include_router(user_routes, prefix="/api/v1")
app.include_router(admin_routes, prefix="/api/v1")
app.include_router(payment_routes, prefix="/api/v1")
app.include_router(product_routes, prefix="/api/v1")
app.include_router(order_routes, prefix="/api/v1")
app.include_router(category_routes, prefix="/api/v1")
app.include_router(review_routes, prefix="/api/v1")


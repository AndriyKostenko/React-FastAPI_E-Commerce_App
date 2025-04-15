import datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, status
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from fastapi.exceptions import ResponseValidationError, RequestValidationError

from src.db.db_setup import init_db
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
                                            UserServiceError, 
                                            UserCreationError, 
                                            UserValidationError, 
                                            UserUpdateError, 
                                            UserDeletionError, 
                                            UserAuthenticationError)

from src.errors.database_errors import (DatabaseConnectionError,
                                        DatabaseTransactionError, 
                                        DatabaseIntegrityError, 
                                        DatabaseTimeoutError,
                                        DatabaseProgrammingError,
                                        DatabaseTableNotFoundError,
                                        DatabaseOperationError)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
    print(f"Server has started at {datetime.datetime.now()}")
    # TODO: Catch an error if the database connection fails
    # Initialize the database connection
    await init_db()
    yield
    print(f"Server has shut down at {datetime.datetime.now()}")


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
    async def validation_input_exception_handler(request: Request, exc: ValidationError):
        errors = [{"field": err['loc'][0], "message": err['msg']} for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": 'Validation input error', "errors": errors}
        )
        
    # Custom Exception handlers for Pydantic validation errors in request and response
    @app.exception_handler(ResponseValidationError)
    async def validation_response_exception_handler(request: Request, exc: ResponseValidationError):
        errors = [{"field": err['loc'][0], "message": err['msg']} for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": 'Validation response error', "errors": errors}
        )

    # Custom Exception handlers for Pydantic validation errors in request and response
    @app.exception_handler(RequestValidationError)
    async def validation_request_exception_handler(request: Request, exc: RequestValidationError):
        errors = [{"field": err['loc'][0], "message": err['msg']} for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": 'Validation request error', "errors": errors}
        )
        
    # Custom Exception handlers for UserCRUDService errors    
    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(request: Request, exc: UserNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)}
        )

    @app.exception_handler(UserAlreadyExistsError)
    async def user_exists_handler(request: Request, exc: UserAlreadyExistsError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserCreationError)
    async def user_creation_error_handler(request: Request, exc: UserCreationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(UserValidationError)
    async def user_validation_error_handler(request: Request, exc: UserValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserUpdateError)
    async def user_update_error_handler(request: Request, exc: UserUpdateError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserDeletionError)
    async def user_deletion_error_handler(request: Request, exc: UserDeletionError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserAuthenticationError)
    async def user_authentication_error_handler(request: Request, exc: UserAuthenticationError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserPasswordError)
    async def user_password_error_handler(request: Request, exc: UserPasswordError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserEmailError)
    async def user_email_error_handler(request: Request, exc: UserEmailError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserServiceDatabaseError)
    async def user_service_database_error_handler(request: Request, exc: UserServiceDatabaseError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(UserIsNotVerifiedError)
    async def user_is_not_verified_handler(request: Request, exc: UserIsNotVerifiedError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)}
        )
        
    # Custom Exception handlers for database errors
    @app.exception_handler(DatabaseConnectionError)
    async def database_connection_error_handler(request: Request, exc: DatabaseConnectionError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )

    @app.exception_handler(DatabaseTransactionError)
    async def database_transaction_error_handler(request: Request, exc: DatabaseTransactionError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
    @app.exception_handler(DatabaseIntegrityError)
    async def database_integrity_error_handler(request: Request, exc: DatabaseIntegrityError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
    @app.exception_handler(DatabaseTimeoutError)
    async def database_timeout_error_handler(request: Request, exc: DatabaseTimeoutError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(DatabaseProgrammingError)
    async def database_programming_error_handler(request: Request, exc: DatabaseProgrammingError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(DatabaseTableNotFoundError)
    async def database_table_not_found_error_handler(request: Request, exc: DatabaseTableNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
        
    @app.exception_handler(DatabaseOperationError)
    async def database_operation_error_handler(request: Request, exc: DatabaseOperationError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
    
        

# adding exception handlers to the app      
add_exception_handlers(app)
        

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://localhost:3001"
]

# Allow all origins (for development purposes, restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins="http://localhost:3000",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Static files configuration
app.mount("/media", StaticFiles(directory="media"), name="media")

# including all the routers to the app
app.include_router(user_routes)
app.include_router(admin_routes)
app.include_router(payment_routes)
app.include_router(product_routes)
app.include_router(order_routes)
app.include_router(category_routes)
app.include_router(review_routes)


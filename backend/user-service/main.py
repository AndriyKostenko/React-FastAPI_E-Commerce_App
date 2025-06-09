from datetime import datetime
from contextlib import asynccontextmanager
from fastapi_cache import FastAPICache

import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from fastapi.exceptions import ResponseValidationError, RequestValidationError

from database import database_session_manager
from routes import user_routes
from errors import (BaseAPIException,
                    DatabaseConnectionError,
                    RateLimitExceededError)
from utils.logger_config import setup_logger
from config import get_settings


# Configure logging
logger = setup_logger(__name__)

# getting the settings from the config file
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
   
    logger.info(f"Server has started at {datetime.now().isoformat()}")
    
    # Use a boolean to track connection success
    db_initialized = False
    
    # Test if engine is initialized
    if database_session_manager.async_engine is not None:
        try:
            # Initialize the database
            await database_session_manager.init_db()
            db_initialized = True
            logger.info(f'Database initialized succesfully at {datetime.now().isoformat()}')
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
    
    logger.info(f"Server has shut down at {datetime.now().isoformat()}")



app = FastAPI(
    title="user-service",
    description="This is a user service for managing users, authentication, and authorization.",
    version="0.0.1",
    lifespan=lifespan
)


@app.middleware("http")
async def host_validation_middleware(request: Request, call_next):
    """
    - Validates the HTTP Host header against the allowed origins.
    - If the request is from a valid host, it proceeds to the next middleware or endpoint.
    - If the request is from an invalid host, it raises a 400 Bad Request error.
    - This middleware is useful for preventing Host header attacks and ensuring that the service only responds to requests from trusted origins.
    - Acts as a first line of defencse against DNS rebinding attacks
    - Works at the HTTP request level before any route handling occurs.
    """
    host = request.headers.get("host", "").split(":")[0]
    if settings.DEBUG_MODE or host in settings.CORS_ALLOWED_ORIGINS:
        response = await call_next(request)
        return response
    
    logger.warning(f"Invalid Host header: {host} from {request.client.host}")
    raise HTTPException(
        status_code=400,
        detail="Invalid Host header",
        headers={"X-Error": "Invalid Host header"}
    )
    
    
def add_exception_handlers(app: FastAPI):
    """
    This function adds exception handlers to the FastAPI application.
    """
   
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        """Custom exception handler for Pydantic validation errors"""
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": [{"field": err["loc"][0], "message": err["msg"]} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )
        
    # Custom Exception handlers for Pydantic validation errors in request and response
    @app.exception_handler(ResponseValidationError)
    async def validation_response_exception_handler(request: Request, exc: ResponseValidationError):
        """Custom exception handler for response validation errors"""
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation response error",
                "errors": [{"field": err["loc"][0], "message": err["msg"]} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )

    # Custom Exception handlers for Pydantic validation errors in request and response
    @app.exception_handler(RequestValidationError)
    async def validation_request_exception_handler(request: Request, exc: RequestValidationError):
        """Custom exception handler for request validation errors""" 
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation request error",
                "errors": [{"field": err["loc"][0], "message": err["msg"]} for err in exc.errors()],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )
    
    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        """Base exception handler for all custom API exceptions"""
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={"detail": exc.detail,
                     "timestamp": datetime.now().isoformat(),
                     "path": request.url.path
            },
        )
        
   
    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_handler(request: Request, exc: RateLimitExceededError):
        """Custom exception handler for rate limit exceeded errors"""
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": exc.detail["message"],
                "retry_after": exc.detail["retry_after"],
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path
            }
        )

        
# adding exception handlers to the app      
add_exception_handlers(app)
        

# CORS or "Cross-Origin Resource Sharing" is a mechanism that 
# allows restricted resources on a web page to be requested from another domain 
# outside the domain from which the first resource was served.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOWED_METHODS,
    allow_headers=settings.CORS_ALLOWED_HEADERS,
)

# Static files configuration
app.mount("/media", StaticFiles(directory="media"), name="media")

# including all the routers to the app
app.include_router(user_routes, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run(app,
                host=settings.APP_HOST,
                port=settings.APP_PORT,
                reload=True)
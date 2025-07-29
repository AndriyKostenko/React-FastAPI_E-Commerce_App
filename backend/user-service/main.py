from datetime import datetime
from contextlib import asynccontextmanager

import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, HTTPException
from pydantic import ValidationError
from fastapi.exceptions import ResponseValidationError, RequestValidationError

from routes.user_routes import user_routes
from routes.admin_routes import admin_routes
from errors.errors import (BaseAPIException,
                            DatabaseConnectionError,
                            RateLimitExceededError)
from shared.shared_instances import (user_service_redis_manager,
                                    user_service_database_session_manager,
                                    logger,
                                    settings)




@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
   
    logger.info(f"Server is starting up on {settings.APP_HOST}:{settings.USER_SERVICE_APP_PORT}...")
    await user_service_redis_manager.health_check()
    await user_service_database_session_manager.init_db()
    logger.info('Server startup complete!')
    
    yield
    
    await user_service_database_session_manager.close()
    logger.warning("Database connection closed on shutdown!")
    await user_service_redis_manager.close()
    logger.warning("Cache connection closed on shutdown!")
    logger.warning(f"Server has shut down !")



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
    if settings.DEBUG_MODE or host in settings.ALLOWED_HOSTS:
        response = await call_next(request)
        return response
    
    logger.warning(f"Invalid Host header: {host} from {request.client.host}")
    raise HTTPException(
        status_code=400,
        detail="Invalid Host header",
        headers={"X-Error": "Invalid Host header"}
    )
    
    
@app.get("/health", tags=["Health Check"])  
async def health_check():
    """
    A simple health check endpoint to verify that the service is running.
    """
    return JSONResponse(
        content={
            "status": "ok", 
            "timestamp": datetime.now().isoformat(),
            "service": "user-service"
        },
        status_code=200,
        headers={"Cache-Control": "no-cache"}
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

# including all the routers to the app
app.include_router(user_routes, prefix="/api/v1")
app.include_router(admin_routes, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run("main:app",
                host=settings.APP_HOST,
                port=settings.USER_SERVICE_APP_PORT,
                reload=True)
import datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is a context manager that will run the startup and shutdown
    events of a FastAPI application.
    """
    print(f"Server has started at {datetime.datetime.now()}")
    await init_db()
    yield
    print(f"Server has shut down at {datetime.datetime.now()}")


app = FastAPI(
    title="E-Commerce API",
    description="An API for user, products and orders for E-commerce",
    version="0.0.1",
    lifespan=lifespan
)

# Custom Exception handlers for Pydantic validation errors in request and response
@app.exception_handler(ValidationError)
async def validation_input_exception_handler(request: Request, exc: ValidationError):
    errors = [{"field": err['loc'][0], "message": err['msg']} for err in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"detail": 'Validation input error', "errors": errors}
    )
    
@app.exception_handler(ResponseValidationError)
async def validation_response_exception_handler(request: Request, exc: ResponseValidationError):
    errors = [{"field": err['loc'][0], "message": err['msg']} for err in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"detail": 'Validation response error', "errors": errors}
    )

@app.exception_handler(RequestValidationError)
async def validation_request_exception_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": err['loc'][0], "message": err['msg']} for err in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"detail": 'Validation request error', "errors": errors}
    )    
    
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

app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(user_routes)
app.include_router(admin_routes)
app.include_router(payment_routes)
app.include_router(product_routes)
app.include_router(order_routes)
app.include_router(category_routes)
app.include_router(review_routes)


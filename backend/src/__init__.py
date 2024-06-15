import datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.db.db_setup import init_db
from src.routes.admin_routes import admin_routes
from src.routes.payment_route import payment_routes
from src.routes.product_route import product_routes
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

app.include_router(user_routes)
app.include_router(admin_routes)
app.include_router(payment_routes)
app.include_router(product_routes)
app.include_router(order_routes)


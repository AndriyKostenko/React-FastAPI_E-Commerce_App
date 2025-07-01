import uvicorn
from fastapi import FastAPI

from routes.user_routes import user_router
from routes.product_routes import product_router
from config import get_settings


app = FastAPI(title="API Gateway")


app.include_router(user_router)
app.include_router(product_router)


if __name__ == "__main__":
    uvicorn.run("main:app",
                host=settings.APP_HOST,
                port=settings.APP_PORT,
                reload=True)
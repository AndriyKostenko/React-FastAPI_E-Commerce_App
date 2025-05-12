import uvicorn
from src.config import settings


if __name__ == "__main__":
    uvicorn.run("src:app",
                host=settings.APP_HOST,
                port=settings.APP_PORT,
                reload=True)

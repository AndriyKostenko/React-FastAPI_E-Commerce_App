from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database_setup import Base, engine
from app.routes import user_routes
from app.routes import auth

app = FastAPI()

# Allow all origins (for development purposes, restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

#including different routers
app.include_router(user_routes.route)
app.include_router(auth.route)


Base.metadata.create_all(bind=engine)
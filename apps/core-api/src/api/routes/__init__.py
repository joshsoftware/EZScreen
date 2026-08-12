from fastapi import APIRouter

from src.api.routes import auth, organizations, system

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(system.router)

from fastapi import APIRouter

from src.api.routes import applications, auth, jobs, organizations, system

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(applications.applicant_router)
api_router.include_router(applications.detail_router)
api_router.include_router(system.router)

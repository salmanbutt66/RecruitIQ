from fastapi import APIRouter

from app.api.v1 import auth, billing, emails, interviews, offers, organizations, positions, resumes

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(positions.router)
api_router.include_router(resumes.router)
api_router.include_router(interviews.router)
api_router.include_router(offers.router)
api_router.include_router(emails.router)
api_router.include_router(billing.router)

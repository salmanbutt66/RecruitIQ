from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.security import configure_logfire, security
# from scripts.seed_platform_admin import seed_platform_admin

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logfire()
    yield


app = FastAPI(
    title="RecruitIQ API",
    description="AI-powered recruitment platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, settings.admin_url, "http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security.handle_errors(app)
# logfire.instrument_fastapi(app)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "recruitiq-api"}



# @app.on_event("startup")
# async def on_startup():
#     await seed_platform_admin()
import uuid

import redis.asyncio as redis
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.enums import JobStatus, JobType
from app.db.models import BackgroundJob
from app.workers.tasks import (
    generate_criteria_task,
    get_redis,
    rejection_feedback_task,
    screen_resumes_task,
    update_job_progress,
)

settings = get_settings()


async def startup(ctx: dict) -> None:
    ctx["redis"] = await get_redis()


async def shutdown(ctx: dict) -> None:
    if "redis" in ctx:
        await ctx["redis"].aclose()


async def run_generate_criteria(ctx: dict, job_id: str, position_id: str) -> dict:
    return await generate_criteria_task(ctx, job_id, position_id)


async def run_screen_resumes(
    ctx: dict, job_id: str, position_id: str, resume_ids: list[str] | None = None
) -> dict:
    return await screen_resumes_task(ctx, job_id, position_id, resume_ids or [])


async def run_rejection_feedback(ctx: dict, job_id: str, candidate_id: str, organization_id: str) -> dict:
    return await rejection_feedback_task(ctx, job_id, candidate_id, organization_id)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [run_generate_criteria, run_screen_resumes, run_rejection_feedback]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = settings.screening_concurrency
    job_timeout = 600

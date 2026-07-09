import json
import uuid

import redis.asyncio as redis
from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import JobStatus, JobType
from app.db.models import BackgroundJob
from app.workers.tasks import get_job_progress, update_job_progress

settings = get_settings()


async def create_job(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    job_type: JobType,
    payload: dict,
    total: int = 1,
) -> BackgroundJob:
    job = BackgroundJob(
        organization_id=organization_id,
        job_type=job_type.value,
        status=JobStatus.PENDING.value,
        progress=0,
        total=total,
        payload=payload,
    )
    db.add(job)
    await db.flush()

    await update_job_progress(
        str(job.id),
        status=JobStatus.PENDING.value,
        progress=0,
        total=total,
        result={},
    )
    return job


async def enqueue_job(job: BackgroundJob) -> None:
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    job_id = str(job.id)
    payload = job.payload

    if job.job_type == JobType.GENERATE_CRITERIA.value:
        await pool.enqueue_job(
            "run_generate_criteria",
            job_id,
            payload["position_id"],
        )
    elif job.job_type == JobType.SCREEN_RESUMES.value:
        await pool.enqueue_job(
            "run_screen_resumes",
            job_id,
            payload["position_id"],
            payload.get("resume_ids", []),
        )
    elif job.job_type == JobType.REJECTION_FEEDBACK.value:
        await pool.enqueue_job(
            "run_rejection_feedback",
            job_id,
            payload["candidate_id"],
            str(job.organization_id),
        )
    await pool.aclose()


async def get_merged_job_status(db: AsyncSession, job_id: uuid.UUID) -> dict | None:
    job = await db.get(BackgroundJob, job_id)
    if not job:
        return None
    redis_data = await get_job_progress(str(job_id))
    base = {
        "id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "total": job.total,
        "payload": job.payload,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
    }
    if redis_data:
        base.update({k: v for k, v in redis_data.items() if k in ("progress", "status", "result", "error", "total")})
    return base

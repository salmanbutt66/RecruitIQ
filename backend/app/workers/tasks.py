import json
import uuid
from datetime import UTC, datetime

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.agents.crews import (
    generate_rejection_feedback,
    review_borderline,
    run_jd_criteria_pipeline,
    parse_resume,
    score_resume,
)
from app.core.config import get_settings
from app.core.enums import JobStatus, JobType, PipelineStatus, ScreeningDecision
from app.db.models import BackgroundJob, Candidate, Position, Resume, ScreeningResult, ScoringCriteria
from app.services.auth_service import create_audit_log
from app.storage.pdf import extract_pdf_text, storage_service

settings = get_settings()


async def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


async def update_job_progress(
    job_id: str,
    *,
    progress: int | None = None,
    status: str | None = None,
    result: dict | None = None,
    error: str | None = None,
    total: int | None = None,
) -> None:
    r = await get_redis()
    key = f"job:{job_id}"
    data = await r.get(key)
    if data:
        payload = json.loads(data)
    else:
        payload = {}
    if progress is not None:
        payload["progress"] = progress
    if status is not None:
        payload["status"] = status
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error
    if total is not None:
        payload["total"] = total
    payload["updated_at"] = datetime.now(UTC).isoformat()
    await r.set(key, json.dumps(payload), ex=86400)


async def get_job_progress(job_id: str) -> dict | None:
    r = await get_redis()
    data = await r.get(f"job:{job_id}")
    return json.loads(data) if data else None


async def generate_criteria_task(ctx: dict, job_id: str, position_id: str) -> dict:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        job = await db.get(BackgroundJob, uuid.UUID(job_id))
        await update_job_progress(job_id, status=JobStatus.RUNNING.value, progress=0, total=2)

        result = await db.execute(
            select(Position).where(Position.id == uuid.UUID(position_id))
        )
        position = result.scalar_one_or_none()
        if not position:
            raise ValueError("Position not found")

        analysis, criteria, model = await run_jd_criteria_pipeline(
            position.job_description, position.designation
        )
        await update_job_progress(job_id, progress=1)

        existing = await db.execute(
            select(ScoringCriteria).where(ScoringCriteria.position_id == position.id)
        )
        sc = existing.scalar_one_or_none()
        criteria_data = [c.model_dump() for c in criteria.criteria]
        if sc:
            sc.jd_analysis = analysis.model_dump()
            sc.criteria = criteria_data
            sc.total_points = 50
            sc.generated_by_model = model
        else:
            sc = ScoringCriteria(
                position_id=position.id,
                jd_analysis=analysis.model_dump(),
                criteria=criteria_data,
                total_points=50,
                generated_by_model=model,
            )
            db.add(sc)

        await create_audit_log(
            db,
            organization_id=position.organization_id,
            user_id=None,
            action="criteria_generated",
            entity_type="position",
            entity_id=str(position.id),
            details={"model": model, "criteria_count": len(criteria_data)},
        )
        if job:
            job.status = JobStatus.COMPLETED.value
            job.progress = 2
            job.total = 2
            job.result = {"criteria_id": str(sc.id)}
        await db.commit()
        await update_job_progress(
            job_id,
            status=JobStatus.COMPLETED.value,
            progress=2,
            total=2,
            result={"criteria_id": str(sc.id)},
        )
        return {"criteria_id": str(sc.id)}


async def screen_resumes_task(ctx: dict, job_id: str, position_id: str, resume_ids: list[str]) -> dict:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        job = await db.get(BackgroundJob, uuid.UUID(job_id))
        position = await db.get(Position, uuid.UUID(position_id))
        if not position:
            raise ValueError("Position not found")

        criteria_result = await db.execute(
            select(ScoringCriteria).where(ScoringCriteria.position_id == position.id)
        )
        scoring_criteria = criteria_result.scalar_one_or_none()
        if not scoring_criteria:
            raise ValueError("Scoring criteria not generated yet")

        if not resume_ids:
            resumes_result = await db.execute(
                select(Resume).where(
                    Resume.organization_id == position.organization_id,
                ).join(Candidate).where(Candidate.position_id == position.id)
            )
            resumes = resumes_result.scalars().all()
            resume_ids = [str(r.id) for r in resumes]

        total = len(resume_ids)
        await update_job_progress(job_id, status=JobStatus.RUNNING.value, progress=0, total=total)
        processed = 0
        results = []

        for resume_id in resume_ids:
            resume = await db.get(Resume, uuid.UUID(resume_id))
            if not resume:
                continue
            candidate = await db.get(Candidate, resume.candidate_id)
            if not candidate:
                continue

            pdf_bytes = storage_service.download_bytes(resume.storage_key)
            if not resume.extracted_text:
                resume.extracted_text = extract_pdf_text(pdf_bytes)

            parsed = await parse_resume(resume.extracted_text)
            resume.extraction_data = parsed
            candidate.full_name = parsed.get("full_name") or candidate.full_name
            candidate.email = parsed.get("email") or candidate.email
            candidate.phone = parsed.get("phone") or candidate.phone
            candidate.location = parsed.get("location") or candidate.location
            candidate.designation = parsed.get("designation") or candidate.designation
            candidate.pipeline_status = PipelineStatus.SCREENING.value

            screening = await score_resume(
                resume.extracted_text,
                position.job_description,
                scoring_criteria.criteria,
                parsed,
            )

            reviewed = False
            if settings.borderline_score_min <= screening.total_score <= settings.borderline_score_max:
                screening = await review_borderline(
                    resume.extracted_text,
                    position.job_description,
                    scoring_criteria.criteria,
                    screening,
                )
                reviewed = True

            existing_sr = await db.execute(
                select(ScreeningResult).where(ScreeningResult.candidate_id == candidate.id)
            )
            sr = existing_sr.scalar_one_or_none()
            sr_data = {
                "total_score": screening.total_score,
                "breakdown": [b.model_dump() for b in screening.breakdown],
                "decision": screening.decision,
                "summary": screening.summary,
                "reason": screening.reason,
                "reviewed_by_openai": reviewed,
                "model_metadata": {"primary": "groq-fast", "reviewed": reviewed},
            }
            if sr:
                for k, v in sr_data.items():
                    setattr(sr, k, v)
            else:
                sr = ScreeningResult(
                    candidate_id=candidate.id,
                    organization_id=position.organization_id,
                    position_id=position.id,
                    **sr_data,
                )
                db.add(sr)

            candidate.pipeline_status = (
                PipelineStatus.SHORTLISTED.value
                if screening.decision == ScreeningDecision.SHORTLIST.value
                else PipelineStatus.REJECTED.value
            )
            processed += 1
            results.append({"candidate_id": str(candidate.id), "score": screening.total_score})
            await db.flush()
            await update_job_progress(job_id, progress=processed, total=total)

        if job:
            job.status = JobStatus.COMPLETED.value
            job.progress = processed
            job.total = total
            job.result = {"screened": processed, "results": results}
        await db.commit()
        await update_job_progress(
            job_id,
            status=JobStatus.COMPLETED.value,
            progress=processed,
            total=total,
            result={"screened": processed, "results": results},
        )
        return {"screened": processed, "results": results}


async def rejection_feedback_task(
    ctx: dict,
    job_id: str,
    candidate_id: str,
    organization_id: str,
) -> dict:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        candidate = await db.get(Candidate, uuid.UUID(candidate_id))
        if not candidate:
            raise ValueError("Candidate not found")
        position = await db.get(Position, candidate.position_id)
        sr_result = await db.execute(
            select(ScreeningResult).where(ScreeningResult.candidate_id == candidate.id)
        )
        sr = sr_result.scalar_one_or_none()

        paragraph = await generate_rejection_feedback(
            candidate_name=candidate.full_name or "Candidate",
            jd_text=position.job_description if position else "",
            screening_summary=sr.summary if sr else "",
            screening_reason=sr.reason if sr else "",
            total_score=sr.total_score if sr else 0,
        )
        await update_job_progress(
            job_id,
            status=JobStatus.COMPLETED.value,
            progress=1,
            total=1,
            result={"paragraph": paragraph, "candidate_id": candidate_id},
        )
        return {"paragraph": paragraph, "candidate_id": candidate_id}

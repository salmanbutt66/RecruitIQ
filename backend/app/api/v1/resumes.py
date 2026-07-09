import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.enums import JobType, PipelineStatus, UserRole
from app.db.models import Candidate, Position, Resume, ScreeningResult, User
from app.db.session import get_db
from app.schemas import (
    BulkCandidateAction,
    CandidateResponse,
    CandidateUpdate,
    CandidateWithScreening,
    JobResponse,
    ResumeResponse,
    ScreeningResultResponse,
    ScreeningStartRequest,
)
from app.services.auth_service import create_audit_log
from app.services.job_service import create_job, enqueue_job
from app.services.subscription_service import check_resume_quota, increment_resume_usage
from app.storage.pdf import extract_pdf_text, storage_service

router = APIRouter(tags=["resumes", "candidates", "screening"])
settings = get_settings()


@router.post("/positions/{position_id}/resumes/bulk", response_model=list[ResumeResponse])
async def bulk_upload_resumes(
    position_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
    files: list[UploadFile] = File(...),
):
    position = await _get_position(db, user, position_id)
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    await check_resume_quota(db, user.organization_id, len(files))

    uploaded = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Only PDF files allowed: {file.filename}")
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        if size > max_bytes:
            raise HTTPException(status_code=400, detail=f"File too large: {file.filename}")

        storage_key, file_size = storage_service.upload_file(file, user.organization_id)
        pdf_bytes = storage_service.download_bytes(storage_key)
        extracted = extract_pdf_text(pdf_bytes)

        candidate = Candidate(
            organization_id=user.organization_id,
            position_id=position.id,
            pipeline_status=PipelineStatus.NEW.value,
        )
        db.add(candidate)
        await db.flush()

        resume = Resume(
            candidate_id=candidate.id,
            organization_id=user.organization_id,
            original_filename=file.filename,
            storage_key=storage_key,
            file_size_bytes=file_size,
            extracted_text=extracted,
        )
        db.add(resume)
        uploaded.append(resume)

    await increment_resume_usage(db, user.organization_id, len(files))
    await create_audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="resumes_uploaded",
        entity_type="position",
        entity_id=str(position.id),
        details={"count": len(files)},
    )
    await db.flush()
    return uploaded


@router.get("/positions/{position_id}/candidates", response_model=list[CandidateWithScreening])
async def list_candidates(
    position_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    decision: str | None = None,
    pipeline_status: str | None = None,
    location: str | None = None,
):
    await _get_position(db, user, position_id)
    query = (
        select(Candidate)
        .options(selectinload(Candidate.screening_result), selectinload(Candidate.resume))
        .where(Candidate.position_id == position_id, Candidate.organization_id == user.organization_id)
    )
    if pipeline_status:
        query = query.where(Candidate.pipeline_status == pipeline_status)
    if location:
        query = query.where(Candidate.location.ilike(f"%{location}%"))

    result = await db.execute(query.order_by(Candidate.created_at.desc()))
    candidates = result.scalars().all()

    if decision:
        candidates = [
            c for c in candidates if c.screening_result and c.screening_result.decision == decision
        ]
    return candidates


@router.patch("/candidates/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: uuid.UUID,
    body: CandidateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    candidate = await _get_candidate(db, user, candidate_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(candidate, field, value)
    await db.flush()
    return candidate


@router.post("/candidates/bulk-action")
async def bulk_candidate_action(
    body: BulkCandidateAction,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    updated = 0
    for cid in body.candidate_ids:
        candidate = await _get_candidate(db, user, cid)
        if body.action == "shortlist":
            candidate.pipeline_status = PipelineStatus.SHORTLISTED.value
        elif body.action == "reject":
            candidate.pipeline_status = PipelineStatus.REJECTED.value
        elif body.action == "interview":
            candidate.pipeline_status = PipelineStatus.INTERVIEW.value
        updated += 1
    return {"updated": updated}


@router.post("/screening/start", response_model=JobResponse)
async def start_screening(
    body: ScreeningStartRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    await _get_position(db, user, body.position_id)
    resume_ids = [str(r) for r in body.resume_ids] if body.resume_ids else []
    total = len(resume_ids) if resume_ids else 1
    job = await create_job(
        db,
        organization_id=user.organization_id,
        job_type=JobType.SCREEN_RESUMES,
        payload={"position_id": str(body.position_id), "resume_ids": resume_ids},
        total=total,
    )
    await enqueue_job(job)
    return job


@router.get("/positions/{position_id}/screening-results", response_model=list[ScreeningResultResponse])
async def list_screening_results(
    position_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    decision: str | None = None,
):
    await _get_position(db, user, position_id)
    query = select(ScreeningResult).where(
        ScreeningResult.position_id == position_id,
        ScreeningResult.organization_id == user.organization_id,
    )
    if decision:
        query = query.where(ScreeningResult.decision == decision)
    result = await db.execute(query.order_by(ScreeningResult.total_score.desc()))
    return result.scalars().all()


@router.get("/resumes/{resume_id}/download-url")
async def get_resume_download_url(
    resume_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.organization_id == user.organization_id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    url = storage_service.get_presigned_url(resume.storage_key)
    return {"url": url}


async def _get_position(db: AsyncSession, user: User, position_id: uuid.UUID) -> Position:
    result = await db.execute(
        select(Position).where(
            Position.id == position_id,
            Position.organization_id == user.organization_id,
        )
    )
    position = result.scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


async def _get_candidate(db: AsyncSession, user: User, candidate_id: uuid.UUID) -> Candidate:
    result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.organization_id == user.organization_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate

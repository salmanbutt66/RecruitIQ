import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.enums import JobType, UserRole
from app.db.models import Candidate, EmailLog, InterviewBatch, Position, ScreeningResult, User
from app.db.session import get_db
from app.schemas import EmailLogResponse, JobResponse, SendEmailRequest
from app.services.email_service import INTERVIEW_TEMPLATE, REJECTION_TEMPLATE, email_service
from app.services.job_service import create_job, enqueue_job, get_merged_job_status
from app.workers.tasks import get_job_progress

router = APIRouter(tags=["emails", "jobs"])


@router.post("/emails/send")
async def send_emails(
    body: SendEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    sent = 0
    for cid in body.candidate_ids:
        result = await db.execute(
            select(Candidate)
            .options(selectinload(Candidate.screening_result))
            .where(Candidate.id == cid, Candidate.organization_id == user.organization_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            continue
        position = await db.get(Position, candidate.position_id)

        if body.template_type == "rejection":
            job = await create_job(
                db,
                organization_id=user.organization_id,
                job_type=JobType.REJECTION_FEEDBACK,
                payload={"candidate_id": str(candidate.id)},
            )
            await enqueue_job(job)
            progress = await get_job_progress(str(job.id))
            paragraph = (progress or {}).get("result", {}).get("paragraph", "")
            if not paragraph and candidate.screening_result:
                paragraph = candidate.screening_result.reason
            html = REJECTION_TEMPLATE.render(
                candidate_name=candidate.full_name or "Candidate",
                position_title=position.title if position else "",
                org_name=user.organization.name,
                feedback_paragraph=paragraph,
            )
            subject = body.custom_subject or f"Application Update - {position.title if position else 'Position'}"
            await email_service.send_email(
                db,
                organization=user.organization,
                candidate=candidate,
                template_type="rejection",
                subject=subject,
                html_body=html,
                user_id=user.id,
            )
            sent += 1

        elif body.template_type == "interview_invitation":
            html = INTERVIEW_TEMPLATE.render(
                candidate_name=candidate.full_name or "Candidate",
                position_title=position.title if position else "",
                scheduled_at="TBD",
                location="TBD",
                notes="Please confirm your availability.",
                org_name=user.organization.name,
            )
            subject = body.custom_subject or f"Interview Invitation - {position.title if position else 'Position'}"
            await email_service.send_email(
                db,
                organization=user.organization,
                candidate=candidate,
                template_type="interview_invitation",
                subject=subject,
                html_body=html,
                user_id=user.id,
            )
            sent += 1

    return {"sent": sent}


@router.get("/emails", response_model=list[EmailLogResponse])
async def list_emails(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(EmailLog)
        .where(EmailLog.organization_id == user.organization_id)
        .order_by(EmailLog.created_at.desc())
        .limit(100)
    )
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    data = await get_merged_job_status(db, job_id)
    if not data:
        raise HTTPException(status_code=404, detail="Job not found")
    return data

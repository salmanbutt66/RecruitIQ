import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from zoneinfo import ZoneInfo

from app.api.deps import get_current_user, require_roles
from app.core.enums import UserRole
from app.db.models import (
    Candidate,
    InterviewBatch,
    InterviewBatchPanelist,
    InterviewEvaluation,
    Organization,
    Position,
    User,
)
from app.db.session import get_db
from app.schemas import (
    EvaluationResponse,
    EvaluationSubmit,
    InterviewBatchCreate,
    InterviewBatchResponse,
    InterviewBatchUpdate,
)
from app.services.auth_service import create_audit_log
from app.services.email_service import INTERVIEW_TEMPLATE, email_service

LOCAL_TZ = ZoneInfo("Asia/Karachi")

router = APIRouter(prefix="/interview-batches", tags=["interviews"])


@router.get("", response_model=list[InterviewBatchResponse])
async def list_batches(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    query = select(InterviewBatch).where(InterviewBatch.organization_id == user.organization_id)
    if user.role == UserRole.PANELIST.value:
        query = query.join(InterviewBatchPanelist).where(
            InterviewBatchPanelist.panelist_id == user.id
        )
    result = await db.execute(query.order_by(InterviewBatch.created_at.desc()))
    return result.scalars().unique().all()


@router.post("", response_model=InterviewBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    body: InterviewBatchCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    position = await _verify_position(db, user, body.position_id)
    batch = InterviewBatch(
        organization_id=user.organization_id,
        position_id=body.position_id,
        name=body.name,
        scheduled_at=body.scheduled_at,
        location=body.location,
        notes=body.notes,
        candidate_order=[str(c) for c in body.candidate_ids],
    )
    db.add(batch)
    await db.flush()

    for panelist_id in body.panelist_ids:
        db.add(InterviewBatchPanelist(batch_id=batch.id, panelist_id=panelist_id))

    candidates: list[Candidate] = []
    for cid in body.candidate_ids:
        candidate = await db.get(Candidate, cid)
        if candidate and candidate.organization_id == user.organization_id:
            candidate.pipeline_status = "interview"
            candidates.append(candidate)

    await create_audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="batch_created",
        entity_type="interview_batch",
        entity_id=str(batch.id),
    )
    # Persist the batch + candidate status changes before attempting any sends,
    # so a Resend failure never costs us the scheduled batch itself.
    await db.commit()
    await db.refresh(batch)

    organization = await db.get(Organization, user.organization_id)
    await _send_interview_invites(
        db,
        organization=organization,
        position_title=position.title,
        batch=batch,
        candidates=candidates,
        user_id=user.id,
    )

    return batch

async def _send_interview_invites(
    db: AsyncSession,
    *,
    organization: Organization,
    position_title: str,
    batch: InterviewBatch,
    candidates: list[Candidate],
    user_id: uuid.UUID,
) -> None:
    scheduled_display = (
        batch.scheduled_at.astimezone(LOCAL_TZ).strftime("%B %d, %Y at %I:%M %p")
        if batch.scheduled_at else "TBD"
    )
    for candidate in candidates:
        if not candidate.email:
            await create_audit_log(
                db,
                organization_id=organization.id,
                user_id=user_id,
                action="interview_email_skipped",
                entity_type="candidate",
                entity_id=str(candidate.id),
                details={"reason": "no_email_on_file", "batch_id": str(batch.id)},
            )
            continue

        html_body = INTERVIEW_TEMPLATE.render(
            candidate_name=candidate.full_name or "Candidate",
            position_title=position_title,
            scheduled_at=scheduled_display,
            location=batch.location or "TBD",
            notes=batch.notes or "",
            org_name=organization.name,
        )
        try:
            await email_service.send_email(
                db,
                organization=organization,
                candidate=candidate,
                template_type="interview_invite",
                subject=f"Interview Invitation: {position_title}",
                html_body=html_body,
                user_id=user_id,
            )
        except Exception as exc:
            await create_audit_log(
                db,
                organization_id=organization.id,
                user_id=user_id,
                action="interview_email_failed",
                entity_type="candidate",
                entity_id=str(candidate.id),
                details={"batch_id": str(batch.id), "error": str(exc)},
            )
    await db.commit()


@router.get("/{batch_id}", response_model=InterviewBatchResponse)
async def get_batch(
    batch_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return await _get_batch(db, user, batch_id)


@router.patch("/{batch_id}", response_model=InterviewBatchResponse)
async def update_batch(
    batch_id: uuid.UUID,
    body: InterviewBatchUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    batch = await _get_batch(db, user, batch_id)
    data = body.model_dump(exclude_unset=True)
    panelist_ids = data.pop("panelist_ids", None)
    candidate_order = data.pop("candidate_order", None)

    for field, value in data.items():
        setattr(batch, field, value)
    if candidate_order is not None:
        batch.candidate_order = [str(c) for c in candidate_order]
    if panelist_ids is not None:
        existing = await db.execute(
            select(InterviewBatchPanelist).where(InterviewBatchPanelist.batch_id == batch.id)
        )
        for p in existing.scalars().all():
            await db.delete(p)
        for pid in panelist_ids:
            db.add(InterviewBatchPanelist(batch_id=batch.id, panelist_id=pid))
    await db.flush()
    return batch


@router.post("/{batch_id}/candidates/{candidate_id}/evaluations", response_model=EvaluationResponse)
async def submit_evaluation(
    batch_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: EvaluationSubmit,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.PANELIST, UserRole.HR_MANAGER, UserRole.ORG_ADMIN))],
):
    batch = await _get_batch(db, user, batch_id)
    if user.role == UserRole.PANELIST.value:
        panelist_check = await db.execute(
            select(InterviewBatchPanelist).where(
                InterviewBatchPanelist.batch_id == batch.id,
                InterviewBatchPanelist.panelist_id == user.id,
            )
        )
        if not panelist_check.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not assigned to this batch")

    overall = sum(item.get("score", 0) for item in body.criteria_scores)
    existing = await db.execute(
        select(InterviewEvaluation).where(
            InterviewEvaluation.batch_id == batch.id,
            InterviewEvaluation.candidate_id == candidate_id,
            InterviewEvaluation.panelist_id == user.id,
        )
    )
    evaluation = existing.scalar_one_or_none()
    eval_data = {
        "criteria_scores": body.criteria_scores,
        "compliance_checks": body.compliance_checks,
        "strengths": body.strengths,
        "weaknesses": body.weaknesses,
        "recommendation": body.recommendation,
        "overall_score": overall,
        "notes": body.notes,
    }
    if evaluation:
        for k, v in eval_data.items():
            setattr(evaluation, k, v)
    else:
        evaluation = InterviewEvaluation(
            batch_id=batch.id,
            candidate_id=candidate_id,
            panelist_id=user.id,
            organization_id=user.organization_id,
            **eval_data,
        )
        db.add(evaluation)
    await db.flush()
    return evaluation


@router.get("/{batch_id}/evaluations", response_model=list[EvaluationResponse])
async def list_evaluations(
    batch_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    batch = await _get_batch(db, user, batch_id)
    query = select(InterviewEvaluation).where(InterviewEvaluation.batch_id == batch.id)
    if user.role == UserRole.PANELIST.value:
        query = query.where(InterviewEvaluation.panelist_id == user.id)
    result = await db.execute(query)
    return result.scalars().all()


async def _verify_position(db: AsyncSession, user: User, position_id: uuid.UUID) -> Position:
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


async def _get_batch(db: AsyncSession, user: User, batch_id: uuid.UUID) -> InterviewBatch:
    result = await db.execute(
        select(InterviewBatch).where(
            InterviewBatch.id == batch_id,
            InterviewBatch.organization_id == user.organization_id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if user.role == UserRole.PANELIST.value:
        panelist_check = await db.execute(
            select(InterviewBatchPanelist).where(
                InterviewBatchPanelist.batch_id == batch.id,
                InterviewBatchPanelist.panelist_id == user.id,
            )
        )
        if not panelist_check.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not assigned to this batch")
    return batch


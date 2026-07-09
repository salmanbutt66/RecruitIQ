import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.enums import JobType, UserRole
from app.db.models import Position, ScoringCriteria, User
from app.db.session import get_db
from app.schemas import (
    JobResponse,
    PositionCreate,
    PositionResponse,
    PositionUpdate,
    ScoringCriteriaResponse,
)
from app.services.auth_service import create_audit_log
from app.services.job_service import create_job, enqueue_job

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionResponse])
async def list_positions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(Position)
        .where(Position.organization_id == user.organization_id)
        .order_by(Position.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
async def create_position(
    body: PositionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    position = Position(
        organization_id=user.organization_id,
        title=body.title,
        job_description=body.job_description,
        designation=body.designation,
        location=body.location,
    )
    db.add(position)
    await create_audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="position_created",
        entity_type="position",
        entity_id=str(position.id),
    )
    await db.flush()
    return position


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    position = await _get_position(db, user, position_id)
    return position


@router.patch("/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: uuid.UUID,
    body: PositionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    position = await _get_position(db, user, position_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(position, field, value)
    await db.flush()
    return position


@router.get("/{position_id}/criteria", response_model=ScoringCriteriaResponse | None)
async def get_criteria(
    position_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    await _get_position(db, user, position_id)
    result = await db.execute(
        select(ScoringCriteria).where(ScoringCriteria.position_id == position_id)
    )
    return result.scalar_one_or_none()


@router.post("/{position_id}/generate-criteria", response_model=JobResponse)
async def generate_criteria(
    position_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    position = await _get_position(db, user, position_id)
    job = await create_job(
        db,
        organization_id=user.organization_id,
        job_type=JobType.GENERATE_CRITERIA,
        payload={"position_id": str(position.id)},
        total=2,
    )
    await enqueue_job(job)
    return job


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

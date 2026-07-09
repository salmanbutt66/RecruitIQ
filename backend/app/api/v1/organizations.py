import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.enums import UserRole
from app.db.models import Candidate, Offer, Organization, Position, User
from app.db.session import get_db
from app.schemas import DashboardStats, OrganizationResponse, OrganizationUpdate

router = APIRouter(tags=["organizations"])


@router.get("/organizations/me", response_model=OrganizationResponse)
async def get_my_organization(
    user: Annotated[User, Depends(get_current_user)],
):
    return user.organization


@router.patch("/organizations/me", response_model=OrganizationResponse)
async def update_my_organization(
    body: OrganizationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN))],
):
    org = user.organization
    if body.name is not None:
        org.name = body.name
    if body.resend_from_email is not None:
        org.resend_from_email = body.resend_from_email
    await db.flush()
    return org


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    org_id = user.organization_id
    open_positions = await db.scalar(
        select(func.count()).select_from(Position).where(
            Position.organization_id == org_id, Position.status == "open"
        )
    )
    total_candidates = await db.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.organization_id == org_id)
    )
    shortlisted = await db.scalar(
        select(func.count()).select_from(Candidate).where(
            Candidate.organization_id == org_id, Candidate.pipeline_status == "shortlisted"
        )
    )
    rejected = await db.scalar(
        select(func.count()).select_from(Candidate).where(
            Candidate.organization_id == org_id, Candidate.pipeline_status == "rejected"
        )
    )
    in_interview = await db.scalar(
        select(func.count()).select_from(Candidate).where(
            Candidate.organization_id == org_id, Candidate.pipeline_status == "interview"
        )
    )
    offers_pending = await db.scalar(
        select(func.count()).select_from(Offer).where(
            Offer.organization_id == org_id, Offer.status.in_(["draft", "sent"])
        )
    )
    return DashboardStats(
        open_positions=open_positions or 0,
        total_candidates=total_candidates or 0,
        shortlisted=shortlisted or 0,
        rejected=rejected or 0,
        in_interview=in_interview or 0,
        offers_pending=offers_pending or 0,
    )

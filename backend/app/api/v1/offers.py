import uuid
from datetime import UTC, datetime
from typing import Annotated
from fastapi.responses import HTMLResponse
from app.core.config import get_settings

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.enums import JobType, PipelineStatus, UserRole
from app.db.models import Candidate, Offer, Position, ScreeningResult, User
from app.db.session import get_db
from app.schemas import OfferCreate, OfferResponse, OfferUpdate
from app.services.auth_service import create_audit_log
from app.services.email_service import OFFER_TEMPLATE, email_service

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("", response_model=list[OfferResponse])
async def list_offers(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(Offer)
        .where(Offer.organization_id == user.organization_id)
        .order_by(Offer.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    body: OfferCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    candidate = await _get_candidate(db, user, body.candidate_id)
    offer = Offer(
        candidate_id=candidate.id,
        organization_id=user.organization_id,
        amount=body.amount,
        currency=body.currency,
        offer_date=body.offer_date,
        notes=body.notes,
        status_history=[{"status": "draft", "at": datetime.now(UTC).isoformat()}],
    )
    db.add(offer)
    candidate.pipeline_status = PipelineStatus.OFFER.value
    await create_audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="offer_created",
        entity_type="offer",
        entity_id=str(offer.id),
    )
    await db.flush()
    return offer


@router.patch("/{offer_id}", response_model=OfferResponse)
async def update_offer(
    offer_id: uuid.UUID,
    body: OfferUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    offer = await _get_offer(db, user, offer_id)
    data = body.model_dump(exclude_unset=True)
    if "status" in data:
        history = list(offer.status_history or [])
        history.append({"status": data["status"], "at": datetime.now(UTC).isoformat()})
        offer.status_history = history
        candidate = await db.get(Candidate, offer.candidate_id)
        if candidate and data["status"] == "accepted":
            candidate.pipeline_status = PipelineStatus.HIRED.value
    for field, value in data.items():
        setattr(offer, field, value)
    await db.flush()
    return offer


settings = get_settings()

@router.post("/{offer_id}/send")
async def send_offer_email(
    offer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN, UserRole.HR_MANAGER))],
):
    offer = await _get_offer(db, user, offer_id)
    candidate = await db.get(Candidate, offer.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    position = await db.get(Position, candidate.position_id)

    base_url = settings.backend_base_url.rstrip("/")
    accept_url = f"{base_url}/api/v1/offers/{offer.id}/respond?decision=accepted"
    reject_url = f"{base_url}/api/v1/offers/{offer.id}/respond?decision=rejected"

    html = OFFER_TEMPLATE.render(
        candidate_name=candidate.full_name or "Candidate",
        position_title=position.title if position else "",
        org_name=user.organization.name,
        amount=offer.amount,
        currency=offer.currency,
        offer_date=offer.offer_date.strftime("%Y-%m-%d"),
        notes=offer.notes or "",
        accept_url=accept_url,
        reject_url=reject_url,
    )
    
    await email_service.send_email(
        db,
        organization=user.organization,
        candidate=candidate,
        template_type="offer",
        subject=f"Offer Letter - {position.title if position else 'Position'}",
        html_body=html,
        user_id=user.id,
    )
    offer.status = "sent"
    history = list(offer.status_history or [])
    history.append({"status": "sent", "at": datetime.now(UTC).isoformat()})
    offer.status_history = history
    return {"status": "sent"}


@router.get("/{offer_id}/respond", include_in_schema=False)
async def respond_to_offer(
    offer_id: uuid.UUID,
    decision: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if decision not in ("accepted", "rejected"):
        return HTMLResponse("<h2>Invalid response link.</h2>", status_code=400)

    result = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        return HTMLResponse("<h2>Offer not found.</h2>", status_code=404)

    if offer.status in ("accepted", "rejected"):
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;text-align:center;padding:60px;'>"
            f"<h2>This offer was already marked as {offer.status}.</h2></body></html>"
        )

    offer.status = decision
    history = list(offer.status_history or [])
    history.append({"status": decision, "at": datetime.now(UTC).isoformat()})
    offer.status_history = history

    candidate = await db.get(Candidate, offer.candidate_id)
    if candidate and decision == "accepted":
        candidate.pipeline_status = PipelineStatus.HIRED.value

    await db.commit()

    verb = "accepted" if decision == "accepted" else "declined"
    return HTMLResponse(
        f"<html><body style='font-family:sans-serif;text-align:center;padding:60px;'>"
        f"<h2>Thank you!</h2><p>We've recorded that you have {verb} this offer.</p>"
        f"</body></html>"
    )

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


async def _get_offer(db: AsyncSession, user: User, offer_id: uuid.UUID) -> Offer:
    result = await db.execute(
        select(Offer).where(Offer.id == offer_id, Offer.organization_id == user.organization_id)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer

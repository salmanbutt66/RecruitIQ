import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.enums import SubscriptionPlan, UserRole
from app.db.models import AuditLog, Candidate, Organization, Subscription, User
from app.db.session import get_db
from app.schemas import AdminOrgResponse, AuditLogResponse, CheckoutSessionResponse, SubscriptionResponse
from app.services.auth_service import get_org_user_count
from app.services.stripe_service import create_billing_portal, create_checkout_session, handle_stripe_webhook
from app.services.subscription_service import get_subscription

router = APIRouter(tags=["billing", "admin"])


@router.get("/billing/subscription", response_model=SubscriptionResponse)
async def get_subscription_info(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    sub = await get_subscription(db, user.organization_id)
    return sub


@router.post("/billing/checkout/{plan}", response_model=CheckoutSessionResponse)
async def checkout(
    plan: SubscriptionPlan,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN))],
):
    url = await create_checkout_session(
        db,
        organization=user.organization,
        plan=plan,
        user_email=user.email,
    )
    return CheckoutSessionResponse(checkout_url=url)


@router.post("/billing/portal", response_model=CheckoutSessionResponse)
async def billing_portal(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ORG_ADMIN))],
):
    url = await create_billing_portal(user.organization, db)
    return CheckoutSessionResponse(checkout_url=url)


@router.post("/billing/webhook")
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
):
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    return await handle_stripe_webhook(db, payload, stripe_signature)


@router.get("/admin/organizations", response_model=list[AdminOrgResponse])
async def admin_list_orgs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.PLATFORM_ADMIN))],
):
    result = await db.execute(select(Organization).order_by(Organization.created_at.desc()))
    orgs = result.scalars().all()
    responses = []
    for org in orgs:
        user_count = await get_org_user_count(db, org.id)
        sub_result = await db.execute(
            select(Subscription).where(Subscription.organization_id == org.id)
        )
        sub = sub_result.scalar_one_or_none()
        resumes_used = sub.resumes_used_this_month if sub else 0
        responses.append(
            AdminOrgResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                is_active=org.is_active,
                resend_from_email=org.resend_from_email,
                user_count=user_count,
                subscription_plan=sub.plan if sub else None,
                resumes_used=resumes_used,
            )
        )
    return responses


@router.patch("/admin/organizations/{org_id}/suspend")
async def suspend_org(
    org_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.PLATFORM_ADMIN))],
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.is_active = False
    return {"status": "suspended"}


@router.get("/admin/audit-logs", response_model=list[AuditLogResponse])
async def admin_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.PLATFORM_ADMIN))],
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)
    )
    return result.scalars().all()

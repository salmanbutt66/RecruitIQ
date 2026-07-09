import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import PLAN_LIMITS, SubscriptionPlan
from app.db.models import Organization, Subscription


async def get_subscription(db: AsyncSession, organization_id: uuid.UUID) -> Subscription:
    result = await db.execute(
        select(Subscription).where(Subscription.organization_id == organization_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(
            organization_id=organization_id,
            plan=SubscriptionPlan.STARTER.value,
            status="active",
            usage_period_start=datetime.now(UTC),
        )
        db.add(sub)
        await db.flush()
    return sub


async def check_resume_quota(db: AsyncSession, organization_id: uuid.UUID, count: int = 1) -> None:
    sub = await get_subscription(db, organization_id)
    plan = SubscriptionPlan(sub.plan)
    limits = PLAN_LIMITS[plan]
    if sub.resumes_used_this_month + count > limits["resumes_per_month"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Resume quota exceeded for {plan.value} plan",
        )


async def increment_resume_usage(db: AsyncSession, organization_id: uuid.UUID, count: int = 1) -> None:
    sub = await get_subscription(db, organization_id)
    sub.resumes_used_this_month += count


async def check_user_quota(db: AsyncSession, organization_id: uuid.UUID, current_count: int) -> None:
    sub = await get_subscription(db, organization_id)
    plan = SubscriptionPlan(sub.plan)
    limits = PLAN_LIMITS[plan]
    if current_count >= limits["users"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"User limit reached for {plan.value} plan",
        )


async def get_org_with_subscription(db: AsyncSession, org_id: uuid.UUID) -> Organization | None:
    result = await db.execute(
        select(Organization)
        .options(selectinload(Organization.subscription))
        .where(Organization.id == org_id)
    )
    return result.scalar_one_or_none()

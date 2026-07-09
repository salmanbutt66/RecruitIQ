import uuid

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import SubscriptionPlan
from app.db.models import Organization, Subscription
from app.services.auth_service import create_audit_log
from app.services.subscription_service import get_subscription

settings = get_settings()


def _init_stripe() -> None:
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key


PLAN_PRICE_MAP = {
    SubscriptionPlan.STARTER: settings.stripe_starter_price_id,
    SubscriptionPlan.PROFESSIONAL: settings.stripe_professional_price_id,
    SubscriptionPlan.ENTERPRISE: settings.stripe_enterprise_price_id,
}


async def create_checkout_session(
    db: AsyncSession,
    *,
    organization: Organization,
    plan: SubscriptionPlan,
    user_email: str,
) -> str:
    _init_stripe()
    price_id = PLAN_PRICE_MAP.get(plan)
    if not settings.stripe_secret_key or not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY and price IDs.",
        )

    sub = await get_subscription(db, organization.id)
    customer_id = sub.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=user_email,
            metadata={"organization_id": str(organization.id)},
        )
        customer_id = customer.id
        sub.stripe_customer_id = customer_id
        await db.commit()  # persist immediately - don't rely on request-scoped auto-commit

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.frontend_url}/settings/billing?success=true",
        cancel_url=f"{settings.frontend_url}/settings/billing?canceled=true",
        metadata={"organization_id": str(organization.id), "plan": plan.value},
    )
    return session.url


async def create_billing_portal(organization: Organization, db: AsyncSession) -> str:
    _init_stripe()
    sub = await get_subscription(db, organization.id)
    if not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found")
    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.frontend_url}/settings/billing",
    )
    return session.url


async def handle_stripe_webhook(db: AsyncSession, payload: bytes, sig_header: str) -> dict:
    _init_stripe()
    if not settings.stripe_webhook_secret:
        return {"status": "ignored"}

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        org_id = session.get("metadata", {}).get("organization_id")
        plan = session.get("metadata", {}).get("plan")
        if org_id:
            sub = await get_subscription(db, uuid.UUID(org_id))
            sub.stripe_subscription_id = session.get("subscription")
            # Stripe customer id should already be set from checkout, but backfill
            # defensively in case this org's subscription record was created another way.
            customer_id = session.get("customer")
            if customer_id and not sub.stripe_customer_id:
                sub.stripe_customer_id = customer_id
            if plan:
                sub.plan = plan
            sub.status = "active"
            await create_audit_log(
                db,
                organization_id=uuid.UUID(org_id),
                user_id=None,
                action="subscription_updated",
                entity_type="subscription",
                entity_id=str(sub.id),
                details={"plan": plan, "event": event["type"]},
            )
            await db.commit()

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
        subscription_obj = event["data"]["object"]
        customer_id = subscription_obj.get("customer")
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = subscription_obj.get("status", sub.status)
            if event["type"] == "customer.subscription.deleted":
                sub.plan = SubscriptionPlan.STARTER.value
            await db.commit()

    return {"status": "processed", "type": event["type"]}